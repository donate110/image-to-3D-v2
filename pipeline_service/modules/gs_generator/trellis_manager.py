from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Optional
import io
import numpy as np

import torch
from PIL import Image, ImageStat

from config import Settings
from logger_config import logger
from libs.trellis2.pipelines import Trellis2ImageTo3DPipeline
from libs.trellis2.utils.mesh_utils import write_ply
from schemas import TrellisResult, TrellisRequest, TrellisParams

class TrellisService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pipeline: Optional[Trellis2ImageTo3DPipeline] = None
        self.gpu = settings.trellis_gpu
        self.default_params = TrellisParams.from_settings(self.settings)

    async def startup(self) -> None:
        logger.info("Loading Trellis2 pipeline...")
        os.environ.setdefault("ATTN_BACKEND", "flash-attn")
        os.environ.setdefault("SPCONV_ALGO", "native")

        if torch.cuda.is_available():
            torch.cuda.set_device(self.gpu)

        self.pipeline = Trellis2ImageTo3DPipeline.from_pretrained(
            self.settings.trellis_model_id
        )
        self.pipeline.cuda()
        logger.success("Trellis2 pipeline ready.")

    async def shutdown(self) -> None:
        self.pipeline = None
        logger.info("Trellis2 pipeline closed.")

    def is_ready(self) -> bool:
        return self.pipeline is not None

    def generate(
        self,
        trellis_request: TrellisRequest,
    ) -> TrellisResult:
        if not self.pipeline:
            raise RuntimeError("Trellis2 pipeline not loaded.")

        image_rgb = trellis_request.image.convert("RGB")
        logger.info(f"Generating Trellis2 {trellis_request.seed=} and image size {trellis_request.image.size}")

        params = self.default_params.overrided(trellis_request.params)

        start = time.time()
        buffer = None
        try:
            # Trellis2 pipeline returns List[MeshWithVoxel]
            # API parameters changed from trellis to trellis2:
            # - slat_sampler_params -> shape_slat_sampler_params + tex_slat_sampler_params
            # - formats removed (trellis2 always outputs mesh)
            mesh_outputs = self.pipeline.run(
                image_rgb,
                seed=trellis_request.seed,
                sparse_structure_sampler_params={
                    "steps": params.sparse_structure_steps,
                    "guidance_strength": params.sparse_structure_cfg_strength,
                },
                shape_slat_sampler_params={
                    "steps": params.shape_slat_steps,
                    "guidance_strength": params.shape_slat_cfg_strength,
                },
                tex_slat_sampler_params={
                    "steps": params.texture_slat_steps,
                    "guidance_strength": params.texture_slat_cfg_strength,
                },
                preprocess_image=False,
                pipeline_type='512',
                num_oversamples=params.num_oversamples,
            )

            generation_time = time.time() - start

            # Get first mesh from output list
            mesh = mesh_outputs[0]

            # Convert mesh to PLY format
            # MeshWithVoxel has vertices and faces attributes (inherited from Mesh class)
            buffer = io.BytesIO()

            # Extract mesh data (vertices, faces) and convert to numpy
            vertices = mesh.vertices.detach().cpu().numpy()
            faces = mesh.faces.detach().cpu().numpy()

            # Validate face shape
            if faces.ndim != 2 or faces.shape[1] not in [3, 4]:
                raise ValueError(f"Invalid face shape: {faces.shape}. Expected [N, 3] or [N, 4]")

            # Extract vertex colors from voxel grid
            vertex_colors = None
            if hasattr(mesh, 'query_vertex_attrs'):
                vertex_attrs = mesh.query_vertex_attrs().detach().cpu().numpy()  # Shape: [N, C]

                # Extract RGB channels based on layout
                if hasattr(mesh, 'layout') and 'base_color' in mesh.layout:
                    rgb_slice = mesh.layout['base_color']
                    vertex_colors_float = vertex_attrs[:, rgb_slice]
                else:
                    # Assume first 3 channels are RGB
                    vertex_colors_float = vertex_attrs[:, :3] if vertex_attrs.shape[1] >= 3 else None

                # Convert from float [0,1] to uint8 [0,255]
                if vertex_colors_float is not None:
                    # Validate shape
                    if vertex_colors_float.ndim != 2 or vertex_colors_float.shape[0] != len(vertices):
                        raise ValueError(f"Color shape mismatch: {vertex_colors_float.shape} vs vertices: {len(vertices)}")
                    if vertex_colors_float.shape[1] not in [3, 4]:
                        raise ValueError(f"Invalid color channels: {vertex_colors_float.shape[1]}. Expected 3 (RGB) or 4 (RGBA)")
                    vertex_colors = (vertex_colors_float * 255).clip(0, 255).astype(np.uint8)

            # Write PLY directly to BytesIO buffer (no temporary file needed)
            write_ply(
                buffer,
                vertices=vertices,
                tris=faces if faces.shape[1] == 3 else np.empty((0, 3), dtype=np.int32),
                quads=faces if faces.shape[1] == 4 else np.empty((0, 4), dtype=np.int32),
                vertex_colors=vertex_colors,
                ascii=False
            )

            buffer.seek(0)

            result = TrellisResult(
                ply_file=buffer.getvalue() if buffer else None # bytes
            )

            logger.success(f"Trellis2 finished generation in {generation_time:.2f}s.")
            return result
        finally:
            if buffer:
                buffer.close()


# CUDA Demo Gallery

Page: [open the rendered CUDA demo gallery](https://htmlpreview.github.io/?https://github.com/BenKnill/blender-workbench/blob/codex/cuda-demo-artifacts/docs/cuda-demo-gallery/index.html)

This directory is a temporary, self-contained gallery for moving CUDA sample
outputs from the RTX 2070 render box to another machine without relying on
local Codex file cards.

If this lands on the repo's GitHub Pages site, the intended page path is:

```text
https://benknill.github.io/blender-workbench/cuda-demo-gallery/
```

## Files

- `index.html` - static gallery page.
- `media/fluidsGL_reference.gif` - bundled NVIDIA fluidsGL reference animation.
- `media/fluidsGL_reference.mp4` - tiny MP4 transcode of that reference GIF.
- `media/cuda_sim_contact.png` - contact sheet made from CUDA sample QA buffers.
- `media/cuda_sim_contact_hold.gif` - GIF preview of the contact sheet.
- `media/cuda_sim_contact_hold.mp4` - small MP4 hold of the contact sheet.
- `media/oceanFFT.png` - visualization of the `oceanFFT -qatest` CUDA/CUFFT height/slope buffers.
- `media/smokeParticles.png` - visualization of the `smokeParticles -qatest` CUDA particle buffers.

## Notes

The interactive `fluidsGL` OpenGL window did not run inside WSLg because the
CUDA/OpenGL interop call failed at `cudaGraphicsGLRegisterBuffer` with
`cudaErrorOperatingSystem`.

The non-interop CUDA paths did run and validate:

- `smokeParticles -qatest` reported `OK` for position and velocity buffers.
- `oceanFFT -qatest` reported `OK` for spatial-domain and slope-shading buffers.

Later cleanup: replace this temporary PR with a GitHub Release or keep the
gallery only if this repo wants generated demo media in history.

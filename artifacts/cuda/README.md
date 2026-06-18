# CUDA demo artifacts

Temporary artifact drop for moving CUDA demo outputs between machines.

These files are not part of the blender-workbench package. They capture the
results from resurrecting local NVIDIA CUDA 11.x sample demos on the RTX 2070
machine.

## Files

- `fluidsGL_reference.gif` - bundled NVIDIA fluidsGL reference animation.
- `fluidsGL_reference.mp4` - tiny MP4 transcode of that reference GIF.
- `cuda_sim_contact.png` - contact sheet made from CUDA sample QA buffers.
- `cuda_sim_contact_hold.gif` - GIF preview of the contact sheet.
- `cuda_sim_contact_hold.mp4` - small MP4 hold of the contact sheet.
- `oceanFFT.png` - visualization of the `oceanFFT -qatest` CUDA/CUFFT height/slope buffers.
- `smokeParticles.png` - visualization of the `smokeParticles -qatest` CUDA particle buffers.

## Notes

The interactive `fluidsGL` OpenGL window did not run inside WSLg because the
CUDA/OpenGL interop call failed at `cudaGraphicsGLRegisterBuffer` with
`cudaErrorOperatingSystem`.

The non-interop CUDA paths did run and validate:

- `smokeParticles -qatest` reported `OK` for position and velocity buffers.
- `oceanFFT -qatest` reported `OK` for spatial-domain and slope-shading buffers.

Later cleanup: replace this temporary PR with a GitHub Release or delete the
branch after the files have been transferred.

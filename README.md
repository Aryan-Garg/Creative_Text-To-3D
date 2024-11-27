# CS839 Course Project: Creative 3D Content Generation 

> Aryan Garg, Avery Gump, Joseph Zhong, Peyman Morteza

--- 

## ToDos

### Implementation

0. Come up with a re-definition for creativity (with the evolution: you could move across domains --> Real or higher creativity at least). 
1. Patch together pipeline: Evolutionary-ConceptLab -> zero123 -> 3DGS  (title: Fast 3D Concept Generation)
2. Get visual (prelim) results from (1)
3. Make nice videos for slides for results from (2) + Get generation times.
4. **@Peyman @Joseph** - Ablation study A - Replace 3DGS with NeRF (Perform steps 1 to 3 for this as well)
5. Implement Epipolar Attention for main (1) (reference: Geo/Fast3DGS and main CVPR paper for epipolar attention)
6. Qualitative study: Vary the number of views vs. fidelity (Figure)
7. Same as (6) but quantitative eval: Do clean-FID, clean-KID and clean-CLIP metrics. (Target dist: Max views)
8. MotionGPT after 3D Reconstruction for plausible motion videos or 4D (valuable open-research - Could be a paper in itself)
9. **@Joseph** - Explore latent space manually

### Writing: 

1. **@Avery @Aryan** - Write abstract & intro
2. **@Peyman @Joseph** - Write related works, experiments (explain the studies and the rationales behind them first then explain results once they are in) & discussion/conclusion. 
3. **@Aryan @Avery** - Methodology

---

## References

1. 3DGS / NeRF (whatever works better)
2. Zero123++ (+/- epipolar)
3. ConceptLab (better VLM?)
4. Geo/F3DGS (https://arxiv.org/pdf/2403.10242)

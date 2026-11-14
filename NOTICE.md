# Credits

Precedent's platform, presenter, benchmark, mockup, deck and UI were built for the event. No ARA or AutoSci source code, data, adapters or runtime is used.

- [Agent-Native Research Artifact](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2) (Orchestra Research, MIT, pinned revision): the idea of keeping dead ends as first-class results with evidence and provenance. Its ResNet example is our pitch story.
- [AutoSci](https://github.com/PKU-DAIR/AutoSci/tree/6bc834a805a1744959a9983809e5d6f0263ef791) (OmegaWiki Contributors, MIT, pinned revision): the idea of revisiting failed ideas only when conditions warrant it.
- [PyTorch](https://pytorch.org), [torchvision](https://github.com/pytorch/vision) and [scikit-learn](https://scikit-learn.org): ResNet-50, the TorchVision ImageNet V1 weights used to initialise calibration, and the digits fixture, used as libraries. Their licenses apply. The repository ships neither checkpoints nor training data.
- Optional local semantic embeddings use [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) through FastEmbed. Model weights are fetched at runtime, not distributed here.
- Pitch statistics on slide 2 of the deck are cited on the slide. Other deck and mockup numbers are illustrative.

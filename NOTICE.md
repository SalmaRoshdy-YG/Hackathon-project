# Credits

Precedent's platform, presenter, synthetic benchmark and rehearsal were built for the event. No ARA or AutoSci source code, data, adapters or runtime is used.

- [Agent-Native Research Artifact](https://github.com/ARA-Labs/Agent-Native-Research-Artifact/tree/e52a925e9d03b4ada3008653e72f99b04116fca2) (Orchestra Research, MIT, pinned revision): keeping dead ends as first-class results with evidence and provenance.
- [AutoSci](https://github.com/PKU-DAIR/AutoSci/tree/6bc834a805a1744959a9983809e5d6f0263ef791) (OmegaWiki Contributors, MIT, pinned revision): revisiting failed ideas only when conditions warrant it.
- Optional local semantic embeddings use [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) through FastEmbed. Model weights are fetched at runtime, not distributed in this repository.
- The live ResNet-50 experiment uses the [scikit-learn digits fixture](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html) and the [TorchVision ResNet-50 ImageNet V1 checkpoint](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet50.html) for its calibration initialization. The repository ships neither checkpoints nor training data.

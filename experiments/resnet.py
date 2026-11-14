"""ResNet-50 transfer experiment on the scikit-learn handwritten digits fixture."""
import argparse
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from platform import python_version
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import uuid4

from platform_api.artifacts import digest
from platform_api.client import connect, require, save
from platform_api.config import utcnow
from platform_api.models import Publish
from platform_api.profile import Experiment

TASK = {"fixture_revision": "sklearn-digits-v1", "dataset": "sklearn digits",
        "architecture": "ResNet-50", "classes": 10, "image_px": 64}
REQUEST = "Train ResNet-50 to at least 80% holdout accuracy on handwritten digits. Find an applicable calibration checkpoint, explain what to avoid, and propose one run."
OPTIONS = {"scratch": (False, .01), "reuse": (True, .01), "high-lr": (True, 10.0)}
DEFAULTS = {"question": REQUEST, "conditions": TASK, "baseline": "scratch"}


def train(job, phase, output, checkpoint=None, image_px=64):
    import sklearn
    import torch
    import torchvision
    from safetensors.torch import load_file, save_file
    from sklearn.datasets import load_digits
    from torch import nn
    from torch.nn.functional import interpolate
    from torchvision.models import ResNet50_Weights, resnet50

    frozen, lr = OPTIONS[job]
    torch.set_num_threads(4)
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    data = load_digits()
    inputs = torch.tensor(data.images, dtype=torch.float32).unsqueeze(1) / 16
    targets = torch.tensor(data.target, dtype=torch.long)
    order = torch.randperm(len(targets), generator=torch.Generator().manual_seed(104))
    windows = {"calibration": (order[:480], order[480:720]),
               "holdout": (order[720:1200], order[1200:1440])}
    train_ids, test_ids = windows[phase]
    fixture = sha256(data.images.tobytes() + data.target.tobytes() + order.numpy().tobytes()).hexdigest()
    model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V1 if frozen and checkpoint is None else None)
    model.fc = nn.Linear(model.fc.in_features, 10)
    if checkpoint is not None:
        model.load_state_dict(load_file(checkpoint))
    if frozen:
        model.requires_grad_(False)
        model.fc.requires_grad_(True)
    model.to(device)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=lr)
    mean = torch.tensor([.485, .456, .406], device=device)[None, :, None, None]
    std = torch.tensor([.229, .224, .225], device=device)[None, :, None, None]

    def batch(ids):
        images = interpolate(inputs[ids].to(device), size=(image_px, image_px), mode="bilinear",
                             align_corners=False).expand(-1, 3, -1, -1)
        return (images - mean) / std, targets[ids].to(device)

    started = perf_counter()
    epochs = 4
    for _ in range(epochs):
        model.train(not frozen)
        for ids in train_ids[torch.randperm(len(train_ids))].split(32):
            x, y = batch(ids)
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(model(x), y)
            loss.backward()
            optimizer.step()
    model.eval()
    correct = 0
    with torch.inference_mode():
        for ids in test_ids.split(32):
            x, y = batch(ids)
            correct += int((model(x).argmax(1) == y).sum())
    elapsed = perf_counter() - started
    accuracy = correct / len(test_ids)
    save_file({name: tensor.detach().cpu() for name, tensor in model.state_dict().items()}, output)
    command = f"python -m experiments.resnet train {job} {phase} output.safetensors --image-px {image_px}"
    if checkpoint is not None:
        command += " --checkpoint input.safetensors"
    return {"run_id": str(uuid4()), "fixture_revision": TASK["fixture_revision"],
            "conditions": {**{k: v for k, v in TASK.items() if k != "fixture_revision"},
                           "image_px": image_px, "split": phase},
            "configuration": {"job_id": job, "epochs": epochs, "learning_rate": lr, "seed": 42,
                              "initialization": "Atlas checkpoint" if checkpoint else
                              ("TorchVision ImageNet V1" if frozen else "random"),
                              "frozen_backbone": frozen, "batch_size": 32, "device": device},
            "execution": "completed", "validity": "valid",
            "direction": "positive" if accuracy >= .8 else "negative",
            "metric": {"name": "top-1 accuracy", "value": accuracy, "unit": "fraction",
                       "operator": ">=", "threshold": .8},
            "elapsed_seconds": round(elapsed, 3), "training_examples": len(train_ids),
            "evaluation_examples": len(test_ids),
            "reproduce": {"command": command, "fixture_sha256": fixture,
                          "versions": {"python": python_version(), "torch": str(torch.__version__),
                                       "torchvision": torchvision.__version__, "sklearn": sklearn.__version__}}}


def finding(receipt, artifact, source, title):
    return Publish(schema_version=1, hypothesis=title, artifact=artifact,
                   **{k: receipt[k] for k in ("fixture_revision", "conditions", "configuration", "metric",
                                              "execution", "validity", "direction")},
                   evidence={"kind": "job_receipt", "data": receipt},
                   source={"system": "resnet-digits", "source_agent": source, "record": receipt["run_id"]},
                   expires_at=utcnow() + timedelta(days=7))


def measure(job, conditions, store, who, sources):
    from platform_api.models import Artifact

    with TemporaryDirectory() as tmp:
        output = Path(tmp) / "resnet50-digits.safetensors"
        checkpoint = None
        source = next((r for r in sources if supports(job, r) and r["direction"] == "positive"), None)
        if job == "reuse":
            if source is None:
                raise ValueError("compatible checkpoint required")
            artifact = Artifact.model_validate(source["artifact"])
            checkpoint = Path(tmp) / "input.safetensors"
            with checkpoint.open("wb+") as dest, store.artifacts.open(who, artifact) as stored:
                while block := stored.read(4 * 1024 * 1024):
                    dest.write(block)
                dest.seek(0)
                if digest(dest) != artifact.sha256:
                    raise ValueError("checkpoint hash mismatch")
        receipt = train(job, "holdout", output, checkpoint)
        receipt["input_checkpoint"] = ({**source["artifact"], "result_id": source["result_id"],
                                        "version": source["version"]} if checkpoint else None)
        # The runner publishes its measured output under a trusted project identity.
        from platform_api.config import Identity
        publisher = Identity(who.project_id, who.agent_id, "publisher")
        with output.open("rb") as file:
            artifact = store.artifacts.put(publisher, output.name, file)
        result = store.publish(publisher, finding(receipt, artifact, who.agent_id,
                               f"ResNet-50 digits holdout · {job} · {receipt['metric']['value']:.1%}"))
        return {**receipt, "published": result, "artifact": artifact.model_dump()}


def supports(job, result):
    artifact = result.get("artifact")
    return (job == "reuse" and result["configuration"].get("job_id") == "reuse"
            and result["conditions"].get("split") == "calibration"
            and artifact is not None and artifact["filename"].endswith(".safetensors"))


def offline(job, conditions):
    raise RuntimeError("the configured runner requires the platform context")


EXPERIMENT = Experiment("resnet50-digits-v1", tuple(OPTIONS), "scratch", tuple(TASK),
                        lambda conditions: conditions == TASK, supports, offline, measure)


def seed():
    rows = [
        ("reuse", 64, "ResNet-50 transfer with a pretrained backbone on 64 px handwritten digits"),
        ("high-lr", 64, "ResNet-50 experiments with a high learning rate on 64 px handwritten digits"),
        ("reuse", 32, "ResNet-50 transfer on a different 32 px image preprocessing task"),
    ]
    with connect(token_env="MEMORY_PUBLISHER_TOKEN") as api, TemporaryDirectory() as tmp:
        output = Path(tmp) / "resnet50-digits.safetensors"
        for job, image_px, title in rows:
            receipt = train(job, "calibration", output, image_px=image_px)
            artifact = None
            if job == "reuse":
                with output.open("rb") as file:
                    artifact = require(api.post("/v1/artifacts", files={"upload": (output.name, file)}))
            ref = require(api.post("/v1/results", json=finding(receipt, artifact, "calibration-agent",
                                                               title).model_dump(mode="json")))
            save({**ref, "job": job, "image_px": image_px, "metric": receipt["metric"], "artifact": artifact})

        crash = Publish(
            schema_version=1,
            hypothesis="ResNet-50 calibration on 64 px handwritten digits interrupted before evaluation",
            fixture_revision=TASK["fixture_revision"],
            conditions={key: value for key, value in TASK.items() if key != "fixture_revision"},
            configuration={"job_id": "reuse"},
            metric={"name": "top-1 accuracy", "value": None, "unit": "fraction",
                    "operator": ">=", "threshold": .8},
            execution="crashed", validity="invalid", direction="undetermined",
            evidence={"kind": "job_receipt", "data": {
                "error": "Seeded example: the training process exited before evaluation.",
            }},
            source={"system": "resnet-digits", "source_agent": "calibration-agent", "record": str(uuid4())},
            expires_at=utcnow() + timedelta(days=7),
        )
        ref = require(api.post("/v1/results", json=crash.model_dump(mode="json")))
        save({**ref, "job": crash.configuration["job_id"], "image_px": crash.conditions["image_px"],
              "execution": crash.execution, "metric": crash.metric.model_dump(), "artifact": None})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed")
    training = commands.add_parser("train")
    training.add_argument("job", choices=OPTIONS)
    training.add_argument("phase", choices=["calibration", "holdout"])
    training.add_argument("output", type=Path)
    training.add_argument("--checkpoint", type=Path)
    training.add_argument("--image-px", type=int, choices=[32, 64], default=64)
    args = parser.parse_args()
    if args.command == "seed":
        seed()
    else:
        save(train(args.job, args.phase, args.output, args.checkpoint, args.image_px))

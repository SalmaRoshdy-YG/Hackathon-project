import time


def train_digits(job, seed=1):
    import torch
    from sklearn.datasets import load_digits
    from sklearn.model_selection import train_test_split
    from torch import nn

    if job not in ("plain", "shortcut"):
        raise ValueError("Unknown training job")
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    digits = load_digits()
    train, test = train_test_split(
        list(range(len(digits.target))),
        test_size=0.25,
        stratify=digits.target,
        random_state=42,
    )
    train, test = torch.tensor(train), torch.tensor(test)
    images = torch.tensor(digits.data / 16, dtype=torch.float32)
    labels = torch.tensor(digits.target, dtype=torch.long)

    start = time.perf_counter()
    stem = nn.Linear(64, 48)
    blocks = nn.ModuleList(
        nn.Sequential(
            nn.Linear(48, 48), nn.BatchNorm1d(48), nn.ReLU(),
            nn.Linear(48, 48), nn.BatchNorm1d(48),
        )
        for _ in range(8)
    )
    head = nn.Linear(48, 10)
    network = nn.ModuleList([stem, blocks, head])

    def predict(batch):
        values = stem(batch).relu()
        for block in blocks:
            update = block(values)
            values = (update + values if job == "shortcut" else update).relu()
        return head(values)

    optimizer = torch.optim.Adam(network.parameters(), lr=0.001)
    for _ in range(15):
        for indices in torch.randperm(len(train)).split(64):
            rows = train[indices]
            optimizer.zero_grad()
            loss = nn.functional.cross_entropy(predict(images[rows]), labels[rows])
            loss.backward()
            optimizer.step()

    network.eval()
    with torch.no_grad():
        correct = int((predict(images[test]).argmax(1) == labels[test]).sum())

    return {
        "job": job,
        "dataset": "sklearn.load_digits",
        "split_seed": 42,
        "training_seed": seed,
        "epochs": 15,
        "parameters": sum(parameter.numel() for parameter in network.parameters()),
        "correct": correct,
        "total": len(test),
        "accuracy": correct / len(test),
        "training_seconds": round(time.perf_counter() - start, 3),
    }

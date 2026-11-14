import argparse

from platform_api.client import connect, require, save


def execute(client, decision_id):
    return require(client.post(f"/v1/decisions/{decision_id}/execute"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--decision", required=True)
    p.add_argument("--base-url")
    p.add_argument("--out")
    a = p.parse_args()
    with connect(a.base_url) as client:
        save(execute(client, a.decision), a.out)


if __name__ == "__main__":
    main()

"""Create local configuration for the guided example."""
from platform_api.setup import main

if __name__ == "__main__":
    main(project_prefix="demo", settings={"MEMORY_EXPERIMENT_MODULE": "benchmark.profile",
        "MEMORY_PRESENTATION_MODULE": "demo.compression", "MEMORY_PLANNER": "rules"})

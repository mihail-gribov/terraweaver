import sys
from pathlib import Path

from terraweaver.agent import solve
from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs

ONTOLOGY_DIR = Path(__file__).parent / "ontology" / "core"


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_task.py '<task description>'")
        sys.exit(1)
    task = sys.argv[1]

    specs = load_specs(ONTOLOGY_DIR)
    classes = build_classes(specs, IMPLS)

    result = solve(task, specs, classes)

    print(f"success: {result.success}")
    print(f"message: {result.message}")
    if result.code:
        print("\n--- code ---")
        print(result.code)
    if result.stdout:
        print("\n--- stdout ---")
        print(result.stdout)
    if result.error:
        print("\n--- error ---")
        print(result.error)


if __name__ == "__main__":
    main()

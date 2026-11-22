"""
What it does: Marks src as a Python package so commands like python -m src.config work.
Why it exists: The benchmark is run as a module from the repo root, not as loose scripts.
What breaks without it: python -m src.config cannot find the package.
Failure stage: none (project setup).
"""

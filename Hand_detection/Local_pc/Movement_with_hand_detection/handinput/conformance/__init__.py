"""Conformance data -- golden vectors and action traces, as language-neutral JSON.

⭐ THE AUTHORITY MOVED HERE, AND THAT IS THE POINT. Python is where this pipeline
is developed and measured; it is no longer what a port has to be "faithful to" by
inspection. `vectors/` pins the arithmetic, `traces/` pins the behaviour over
time, and any implementation in any language passes or fails the same files.

    generate_vectors.py   regenerate vectors/   (after an INTENTIONAL change)
    generate_traces.py    regenerate traces/    (same rule)
    analysis/verify_handinput.py                run them against this code

⛔ Regenerating to turn a suite green throws away the only thing these files are
for. A regeneration belongs in a commit that names the behaviour that changed.
"""

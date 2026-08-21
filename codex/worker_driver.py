"""Worker driver: drives a Codex thread inside a writable sandbox.

The Worker designs APIs, edits code, adds tests, runs pytest, debugs and
commits the candidate. Its "done" only means the candidate is ready for
inspection, not that the Work Order is complete.
"""


def run_worker_task(work_order_id: str, task: str):
    raise NotImplementedError

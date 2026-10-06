__version__ = "5.0.2"

# Imported on first use, not at import time: eagerly importing these pulled in bs4,
# docker, datasets and modal, so `import swebench` cost seconds and failed outright
# when an optional dependency was missing (#525).
_LAZY_IMPORTS = {
    "build_dataset": ("swebench.collect.build_dataset", "main"),
    "get_tasks_pipeline": ("swebench.collect.get_tasks_pipeline", "main"),
    "print_pulls": ("swebench.collect.print_pulls", "main"),
    "SWEbenchInstance": ("swebench.types", "SWEbenchInstance"),
    "build_instance_images": ("swebench.image_builder", "build_instance_images"),
    "build_instance_image": ("swebench.image_builder", "build_instance_image"),
    "cleanup_container": ("swebench.harness.docker_utils", "cleanup_container"),
    "copy_to_container": ("swebench.harness.docker_utils", "copy_to_container"),
    "exec_run_with_timeout": ("swebench.harness.docker_utils", "exec_run_with_timeout"),
    "compute_fail_to_pass": ("swebench.harness.grading", "compute_fail_to_pass"),
    "compute_pass_to_pass": ("swebench.harness.grading", "compute_pass_to_pass"),
    "get_eval_report": ("swebench.harness.grading", "get_eval_report"),
    "get_resolution_status": ("swebench.harness.grading", "get_resolution_status"),
    "ResolvedStatus": ("swebench.harness.grading", "ResolvedStatus"),
    "TestStatus": ("swebench.harness.grading", "TestStatus"),
    "PARSER_REGISTRY": ("swebench.harness.log_parsers", "PARSER_REGISTRY"),
    "run_evaluation": ("swebench.harness.run_evaluation", "main"),
    "run_threadpool": ("swebench.harness.utils", "run_threadpool"),
    "VettoContainer": ("swebench.harness.vetto_adapter", "VettoContainer"),
    "VettoTaskRunner": ("swebench.harness.vetto_adapter", "VettoTaskRunner"),
}

__all__ = [
    "PARSER_REGISTRY",
    "ResolvedStatus",
    "SWEbenchInstance",
    "TestStatus",
    "VettoContainer",
    "VettoTaskRunner",
    "__version__",
    "build_dataset",
    "build_instance_image",
    "build_instance_images",
    "cleanup_container",
    "compute_fail_to_pass",
    "compute_pass_to_pass",
    "copy_to_container",
    "exec_run_with_timeout",
    "get_eval_report",
    "get_resolution_status",
    "get_tasks_pipeline",
    "print_pulls",
    "run_evaluation",
    "run_threadpool",
]


def __getattr__(name: str):
    try:
        module_path, attr = _LAZY_IMPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    import importlib

    value = getattr(importlib.import_module(module_path), attr)
    globals()[name] = value  # cache so later lookups skip this path
    return value


def __dir__():
    return sorted(__all__)

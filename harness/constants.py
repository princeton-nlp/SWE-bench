MAP_VERSION_TO_INSTALL_SKLEARN = {
    k: {
        "python": "3.6",
        "packages": "numpy scipy cython pytest pandas matplotlib",
        "install": "pip install -v --no-use-pep517 --no-build-isolation -e .",
    }
    for k in ["0.20", "0.21", "0.22"]
}
MAP_VERSION_TO_INSTALL_SKLEARN.update(
    {
        k: {
            "python": "3.7",
            "packages": "numpy scipy cython pytest pandas matplotlib",
            "install": "pip install -v --no-use-pep517 --no-build-isolation -e .",
        }
        for k in ["0.23", "0.24"]
    }
)
MAP_VERSION_TO_INSTALL_SKLEARN.update(
    {
        k: {
            "python": "3.9",
            "packages": "numpy scipy cython pytest pandas matplotlib joblib threadpoolctl",
            "install": "pip install -v --no-use-pep517 --no-build-isolation -e .",
        }
        for k in ["1.0", "1.1", "1.2", "1.3", "1.4"]
    }
)

MAP_VERSION_TO_INSTALL_FLASK = {
    "0.11-dev": {
        "python": "3.6",
        "packages": "pytest",
        "pip_packages": "tox",
        "install": "python setup.py develop",
    },
    "1.0": {
        "python": "3.8",
        "packages": "pytest",
        "pip_packages": "tox",
        "install": 'pip install -e ".[dev]"',
    },
    "1.1": {
        "python": "3.9",
        "packages": "pytest",
        "pip_packages": "tox",
        "install": 'pip install -e ".[dev]"',
    },
    "2.0": {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "pip install -e .",
    },
    "2.1": {
        "python": "3.10",
        "packages": "requirements.txt",
        "install": "pip install -e .",
    },
}
MAP_VERSION_TO_INSTALL_FLASK.update(
    {
        k: {
            "python": "3.6",
            "packages": "pytest",
            "pip_packages": "tox",
            "install": "pip install -e .",
        }
        for k in ["0.11", "0.12", "0.12-dev", "0.13-dev"]
    }
)
MAP_VERSION_TO_INSTALL_FLASK.update(
    {
        k: {
            "python": "3.11",
            "packages": "requirements.txt",
            "install": "pip install -e .",
        }
        for k in ["2.2", "2.3"]
    }
)

MAP_VERSION_TO_INSTALL_DJANGO = {
    k: {
        "python": "3.5",
        "packages": "requirements.txt",
        "install": "python setup.py install",
    }
    for k in ["1.7", "1.8", "1.9", "1.10", "1.11", "2.0", "2.1", "2.2"]
}
MAP_VERSION_TO_INSTALL_DJANGO.update(
    {
        k: {"python": "3.5", "install": "python setup.py install"}
        for k in ["1.4", "1.5", "1.6"]
    }
)
MAP_VERSION_TO_INSTALL_DJANGO.update(
    {
        k: {
            "python": "3.6",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
        }
        for k in ["3.0", "3.1", "3.2"]
    }
)
MAP_VERSION_TO_INSTALL_DJANGO.update(
    {
        k: {
            "python": "3.8",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
        }
        for k in ["4.0"]
    }
)
MAP_VERSION_TO_INSTALL_DJANGO.update(
    {
        k: {
            "python": "3.9",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
        }
        for k in ["4.1", "4.2"]
    }
)
MAP_VERSION_TO_INSTALL_DJANGO.update(
    {
        k: {
            "python": "3.11",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
        }
        for k in ["5.0"]
    }
)

MAP_VERSION_TO_INSTALL_REQUESTS = {
    k: {"python": "3.9", "packages": "pytest", "install": "python -m pip install ."}
    for k in
        ["0.7", "0.8", "0.9", "0.11", "0.13", "0.14", "1.1", "1.2", "2.0", "2.2"] + \
        ["2.3", "2.4", "2.5", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12", "2.17"] + \
        ["2.18", "2.19", "2.22", "2.26", "2.25", "2.27", "3.0"]
}

MAP_VERSION_TO_INSTALL_SEABORN = {
    k: {"python": "3.9", "install": "pip install -e .", "pip_packages": "pytest"}
    for k in ["0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "0.11"]
}
MAP_VERSION_TO_INSTALL_SEABORN.update(
    {k: {"python": "3.9", "install": "pip install -e .[dev]"} for k in ["0.12", "0.13"]}
)

MAP_VERSION_TO_INSTALL_PYTEST = {
    k: {"python": "3.9", "install": "pip install -e ."}
    for k in ["3.10", "6.0", "6.2", "6.3", "8.0"]
    + [
        str(round(0.1 * x, 1))
        for interval in [(30, 47), (50, 55), (70, 75)]
        for x in range(interval[0], interval[1], 1)
    ]
}

MAP_VERSION_TO_INSTALL_MATPLOTLIB = {
    k: {
        "python": "3.9",
        "packages": "environment.yml",
        "install": "python -m pip install -e .",
    }
    for k in ["3.5", "3.6", "3.7"]
}
MAP_VERSION_TO_INSTALL_MATPLOTLIB.update(
    {
        k: {
            "python": "3.8",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
        }
        for k in ["3.1", "3.2", "3.3", "3.4"]
    }
)
MAP_VERSION_TO_INSTALL_MATPLOTLIB.update(
    {
        k: {
            "python": "3.7",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
        }
        for k in ["3.0"]
    }
)
MAP_VERSION_TO_INSTALL_MATPLOTLIB.update(
    {
        k: {
            "python": "3.5",
            "install": "python setup.py build; python setup.py install",
        }
        for k in ["2.0", "2.1", "2.2", "1.0", "1.1", "1.2", "1.3", "1.4", "1.5"]
    }
)

MAP_VERSION_TO_INSTALL_SPHINX = {
    k: {
        "python": "3.9",
        "pip_packages": "tox",
        "install": "pip install -e .[test]",
        "pre_install": ["sed -i 's/pytest/pytest -rA/' tox.ini"],
    } for k in
        ["1.5", "1.6", "1.7", "1.8", "2.0", "2.1", "2.2", "2.3", "2.4", "3.0"] + \
        ["3.1", "3.2", "3.3", "3.4", "3.5", "4.0", "4.1", "4.2", "4.3", "4.4"] + \
        ["4.5", "5.0", "5.1", "5.2", "5.3", "6.0", "6.2", "7.0", "7.1", "7.2"]
}
for k in ["3.0", "3.1", "3.2", "3.3", "3.4", "3.5", "4.0"]:
    MAP_VERSION_TO_INSTALL_SPHINX[k][
        "pre_install"
    ].append("sed -i 's/Jinja2>=2.3/Jinja2<3.1/' setup.py")

MAP_VERSION_TO_INSTALL_ASTROPY = {
    k: {"python": "3.9", "install": "pip install -e .[test]"}
    for k in
        ["0.1", "0.2", "0.3", "0.4", "1.1", "1.2", "1.3", "3.0", "3.1", "3.2"] + \
        ["4.1", "4.2", "4.3", "5.0", "5.1", "5.2"]
}

MAP_VERSION_TO_INSTALL_SYMPY = {
    k: {
        "python": "3.9",
        "packages": "mpmath flake8",
        "pip_packages": "flake8-comprehensions",
        "install": "pip install -e .",
    }
    for k in
        ["0.7", "1.0", "1.1", "1.10", "1.11", "1.12", "1.2", "1.4", "1.5", "1.6"] + \
        ["1.7", "1.8", "1.9"]
}
MAP_VERSION_TO_INSTALL_SYMPY.update(
    {
        k: {
            "python": "3.9",
            "packages": "requirements.txt",
            "install": "pip install -e .",
        }
        for k in ["1.13"]
    }
)

MAP_VERSION_TO_INSTALL_PYLINT = {
    k: {"python": "3.9", "packages": "requirements.txt", "install": "pip install -e ."}
    for k in ["2.10", "2.11", "2.13", "2.14", "2.15", "2.16", "2.17", "2.8", "2.9", "3.0"]
}

MAP_VERSION_TO_INSTALL_XARRAY = {
    k: {
        "python": "3.10",
        "packages": "environment.yml",
        "install": "pip install -e .",
        "pip_packages": "pytest",
        "no_use_env": True,
    }
    for k in ["0.12", "0.18", "0.19", "0.20", "2022.03", "2022.06", "2022.09"]
}

# Constants - Task Instance Instllation Environment
MAP_VERSION_TO_INSTALL = {
    "astropy/astropy": MAP_VERSION_TO_INSTALL_ASTROPY,
    "django/django": MAP_VERSION_TO_INSTALL_DJANGO,
    "matplotlib/matplotlib": MAP_VERSION_TO_INSTALL_MATPLOTLIB,
    "mwaskom/seaborn": MAP_VERSION_TO_INSTALL_SEABORN,
    "pallets/flask": MAP_VERSION_TO_INSTALL_FLASK,
    "psf/requests": MAP_VERSION_TO_INSTALL_REQUESTS,
    "pydata/xarray": MAP_VERSION_TO_INSTALL_XARRAY,
    "pylint-dev/pylint": MAP_VERSION_TO_INSTALL_PYLINT,
    "pytest-dev/pytest": MAP_VERSION_TO_INSTALL_PYTEST,
    "scikit-learn/scikit-learn": MAP_VERSION_TO_INSTALL_SKLEARN,
    "sphinx-doc/sphinx": MAP_VERSION_TO_INSTALL_SPHINX,
    "sympy/sympy": MAP_VERSION_TO_INSTALL_SYMPY,
}

# Constants - Repository Specific Installation Instructions
MAP_REPO_TO_INSTALL = {}

# Constants - Task Instance Test Frameworks
TEST_PYTEST = "pytest --no-header -rA --tb=no -p no:cacheprovider"
MAP_REPO_TO_TEST_FRAMEWORK = {
    "astropy/astropy": TEST_PYTEST,
    "django/django": "./tests/runtests.py --verbosity 2",
    "matplotlib/matplotlib": TEST_PYTEST,
    "mwaskom/seaborn": "pytest --no-header -rA",
    "pallets/flask": TEST_PYTEST,
    "psf/requests": TEST_PYTEST,
    "pydata/xarray": TEST_PYTEST,
    "pylint-dev/pylint": TEST_PYTEST,
    "pytest-dev/pytest": "pytest -rA",
    "scikit-learn/scikit-learn": TEST_PYTEST,
    "sphinx-doc/sphinx": "tox -epy39 -v --",
    "sympy/sympy": "bin/test -C --verbose",
}

# Constants - Task Instance Version Extraction
MAP_REPO_TO_VERSION_PATHS = {
    "django/django": ["django/__init__.py"],
    "mwaskom/seaborn": ["seaborn/__init__.py"],
    "pallets/flask": ["src/flask/__init__.py", "flask/__init__.py"],
    "psf/requests": ["requests/__version__.py", "requests/__init__.py"],
    "pyca/cryptography": [
        "src/cryptography/__about__.py",
        "src/cryptography/__init__.py",
    ],
    "pylint-dev/pylint": ["pylint/__pkginfo__.py", "pylint/__init__.py"],
    "pytest-dev/pytest": ["src/_pytest/_version.py", "_pytest/_version.py"],
    "Qiskit/qiskit": ["qiskit/VERSION.txt"],
    "scikit-learn/scikit-learn": ["sklearn/__init__.py"],
    "sphinx-doc/sphinx": ["sphinx/__init__.py"],
    "sympy/sympy": ["sympy/release.py", "sympy/__init__.py"],
}

MAP_REPO_TO_VERSION_PATTERNS = {
    k: [r'__version__ = [\'"](.*)[\'"]', r"VERSION = \((.*)\)"]
    for k in [
        "scikit-learn/scikit-learn",
        "pallets/flask",
        "django/django",
        "psf/requests",
        "mwaskom/seaborn",
        "pyca/cryptography",
        "sphinx-doc/sphinx",
        "sympy/sympy",
        "pylint-dev/pylint",
    ]
}
MAP_REPO_TO_VERSION_PATTERNS.update(
    {
        k: [
            r'__version__ = [\'"](.*)[\'"]',
            r'__version__ = version = [\'"](.*)[\'"]',
            r"VERSION = \((.*)\)",
        ]
        for k in ["pytest-dev/pytest", "matplotlib/matplotlib"]
    }
)
MAP_REPO_TO_VERSION_PATTERNS.update({k: [r"(.*)"] for k in ["Qiskit/qiskit"]})

# Constants - Task Instance Requirements File Paths
MAP_REPO_TO_REQS_PATHS = {
    "django/django": ["tests/requirements/py3.txt"],
    "matplotlib/matplotlib": ["requirements/dev/dev-requirements.txt", "requirements/testing/travis_all.txt"],
    "pallets/flask": ["requirements/dev.txt"],
    "pylint-dev/pylint": ["requirements_test.txt"],
    "sympy/sympy": ["requirements-dev.txt"],
}

# Constants - Task Instance environment.yml File Paths
MAP_REPO_TO_ENV_YML_PATHS = {
    "matplotlib/matplotlib": ["environment.yml"],
    "pydata/xarray": ["ci/requirements/environment.yml", "environment.yml"],
}

# Constants - Evaluation Keys
KEY_INSTANCE_ID = "instance_id"
KEY_MODEL = "model"
KEY_PREDICTION = "prediction"

# Constants - Logging
APPLY_PATCH_FAIL = ">>>>> Patch Apply Failed"
APPLY_PATCH_PASS = ">>>>> Applied Patch"
INSTALL_FAIL = ">>>>> Init Failed"
INSTALL_PASS = ">>>>> Init Succeeded"
INSTALL_TIMEOUT = ">>>>> Init Timed Out"
RESET_FAILED = ">>>>> Reset Failed"
TESTS_ERROR = ">>>>> Tests Errored"
TESTS_FAILED = ">>>>> Some Tests Failed"
TESTS_PASSED = ">>>>> All Tests Passed"
TESTS_TIMEOUT = ">>>>> Tests Timed Out"

# Constants - Miscellaneous
NON_TEST_EXTS = [".json", ".png", "csv", ".txt", ".md", ".jpg", ".jpeg", ".pkl", ".yml", ".yaml", ".toml"]
SWE_BENCH_URL_RAW = "https://raw.githubusercontent.com/"
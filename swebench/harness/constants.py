MAP_VERSION_TO_INSTALL_SKLEARN = {
    k: {
        "python": "3.6",
        "packages": "numpy scipy cython pytest pandas matplotlib",
        "install": "pip install -v --no-use-pep517 --no-build-isolation -e .",
        "arch_specific_packages": {
            "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
        }
    }
    for k in ["0.20", "0.21", "0.22"]
}
MAP_VERSION_TO_INSTALL_SKLEARN.update(
    {
        k: {
            "python": "3.7",
            "packages": "numpy scipy cython pytest pandas matplotlib",
            "install": "pip install -v --no-use-pep517 --no-build-isolation -e .",
            "arch_specific_packages": {
                "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
            }
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
            "arch_specific_packages": {
                "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
            }
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
        "pip_packages": "Werkzeug==2.2.2",
    },
    "2.1": {
        "python": "3.10",
        "packages": "requirements.txt",
        "install": "pip install -e .",
        "pip_packages": "Werkzeug==2.2.2",
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
            "pip_packages": "Werkzeug==2.2.2"
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
        "python": "3.11",
        "packages": "environment.yml",
        "install": "python -m pip install -e .",
        "pip_packages": " ".join([
            "contourpy==1.1.0",
            "cycler==0.11.0",
            "fonttools==4.42.1",
            "kiwisolver==1.4.5",
            "numpy==1.25.2",
            "packaging==23.1",
            "pillow==10.0.0",
            "pyparsing==3.0.9",
            "python-dateutil==2.8.2",
            "six==1.16.0",
            "setuptools==68.1.2",
            "setuptools-scm==7.1.0",
            "typing-extensions==4.7.1",
        ]),
        "arch_specific_packages": {
            "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
        }
    }
    for k in ["3.5", "3.6", "3.7"]
}
MAP_VERSION_TO_INSTALL_MATPLOTLIB.update(
    {
        k: {
            "python": "3.8",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
            "arch_specific_packages": {
                "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
            }
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
            "arch_specific_packages": {
                "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
            }
        }
        for k in ["3.0"]
    }
)
MAP_VERSION_TO_INSTALL_MATPLOTLIB.update(
    {
        k: {
            "python": "3.5",
            "install": "python setup.py build; python setup.py install",
            "arch_specific_packages": {
                "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
            }
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
        "arch_specific_packages": {
            "aarch64": "gxx_linux-aarch64 gcc_linux-aarch64 make",
            "x86_64": "gxx_linux-64 gcc_linux-64 make",
        }
    } for k in
        ["1.5", "1.6", "1.7", "1.8", "2.0", "2.1", "2.2", "2.3", "2.4", "3.0"] + \
        ["3.1", "3.2", "3.3", "3.4", "3.5", "4.0", "4.1", "4.2", "4.3", "4.4"] + \
        ["4.5", "5.0", "5.1", "5.2", "5.3", "6.0", "6.2", "7.0", "7.1", "7.2"]
}
for k in ["3.0", "3.1", "3.2", "3.3", "3.4", "3.5", "4.0", "4.1", "4.2", "4.3", "4.4"]:
    MAP_VERSION_TO_INSTALL_SPHINX[k][
        "pre_install"
    ].extend([
        "sed -i 's/Jinja2>=2.3/Jinja2<3.0/' setup.py",
        "sed -i 's/sphinxcontrib-applehelp/sphinxcontrib-applehelp<=1.0.7/' setup.py",
        "sed -i 's/sphinxcontrib-devhelp/sphinxcontrib-devhelp<=1.0.5/' setup.py",
        "sed -i 's/sphinxcontrib-qthelp/sphinxcontrib-qthelp<=1.0.6/' setup.py",
        "sed -i 's/alabaster>=0.7,<0.8/alabaster>=0.7,<0.7.12/' setup.py",
        'sed -i "s/\'packaging\',/\'packaging\', \'markupsafe<=2.0.1\',/" setup.py',
    ])
    if k in ["4.2", "4.3", "4.4"]:
        MAP_VERSION_TO_INSTALL_SPHINX[k]["pre_install"].extend([
            "sed -i 's/sphinxcontrib-htmlhelp>=2.0.0/sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4/' setup.py",
            "sed -i 's/sphinxcontrib-serializinghtml>=1.1.5/sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9/' setup.py",
        ])
    elif k == "4.1":
        MAP_VERSION_TO_INSTALL_SPHINX[k]["pre_install"].extend([
            (
                "grep -q 'sphinxcontrib-htmlhelp>=2.0.0' setup.py && "
                "sed -i 's/sphinxcontrib-htmlhelp>=2.0.0/sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4/' setup.py || "
                "sed -i 's/sphinxcontrib-htmlhelp/sphinxcontrib-htmlhelp<=2.0.4/' setup.py"
            ),
            (
                "grep -q 'sphinxcontrib-serializinghtml>=1.1.5' setup.py && "
                "sed -i 's/sphinxcontrib-serializinghtml>=1.1.5/sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9/' setup.py || "
                "sed -i 's/sphinxcontrib-serializinghtml/sphinxcontrib-serializinghtml<=1.1.9/' setup.py"
            )
        ])
    else:
        MAP_VERSION_TO_INSTALL_SPHINX[k]["pre_install"].extend([
            "sed -i 's/sphinxcontrib-htmlhelp/sphinxcontrib-htmlhelp<=2.0.4/' setup.py",
            "sed -i 's/sphinxcontrib-serializinghtml/sphinxcontrib-serializinghtml<=1.1.9/' setup.py",
        ])


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
MAP_VERSION_TO_INSTALL_PYLINT.update({
    k: {**MAP_VERSION_TO_INSTALL_PYLINT[k], "pip_packages": " ".join([
        "astroid==3.0.0a7"
    ])} for k in ['3.0']})

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

MAP_VERSION_TO_INSTALL_TRANSFORMERS = {
    k: {
        "python": "3.10",
        "install": "pip install -e .",
        "pip_packages": "pytest torch tensorflow flax",
    }
    for k in [
        '4.28', '4.29', '4.30', '4.31', '4.32', '4.16', '4.14', '4.15', '4.17',
        '4.19', '4.18', '4.22', '4.20', '4.11', '4.13', '4.12', '4.6', '4.7',
        '4.9', '4.8', '4.10', '3.1', '3.2', '3.4', '3.3', '4.0', '3.5', '4.1',
        '2.5', '2.8', '2.9', '2.11', '2.10', '3.0', '4.3', '4.2', '4.5', '4.4',
        '4.21', '4.23', '4.24', '4.26', '4.25', '4.27'
    ]
}

MAP_VERSION_TO_INSTALL_SQLFLUFF = {
    k: {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "pip install -e .",
    }
    for k in [
        '0.10', '0.11', '0.12', '0.13', '0.4', '0.5', '0.6', '0.8', '0.9',
        '1.0', '1.1', '1.2', '1.3', '1.4', '2.0', '2.1', '2.2'
    ]
}

MAP_VERSION_TO_INSTALL_DBT_CORE = {
    k: {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "pip install -e .",
    }
    for k in [
        '0.13', '0.14', '0.15', '0.16', '0.17', '0.18', '0.19', '0.20',
        '0.21', '1.0', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7'
    ]
}

MAP_VERSION_TO_INSTALL_PYVISTA = {
    k: {
        "python": "3.9",
        "install": "pip install -e .",
        "pip_packages": "pytest",
    }
    for k in ['0.20', '0.21', '0.22', '0.23']
}
MAP_VERSION_TO_INSTALL_PYVISTA.update({
    k: {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "pip install -e .",
        "pip_packages": "pytest",
    }
    for k in [
        '0.24', '0.25', '0.26', '0.27', '0.28', '0.29', '0.30', '0.31',
        '0.32', '0.33', '0.34', '0.35', '0.36', '0.37', '0.38', '0.39',
        '0.40', '0.41', '0.42', '0.43'
    ]
})

MAP_VERSION_TO_INSTALL_ASTROID = {
    k: {
        "python": "3.9",
        "install": "pip install -e .",
        "pip_packages": "pytest",
    }
    for k in [
        '2.10', '2.12', '2.13', '2.14', '2.15', '2.16', '2.5', '2.6',
        '2.7', '2.8', '2.9', '3.0'
    ]
}

MAP_VERSION_TO_INSTALL_MARSHMALLOW = {
    k: {
        "python": "3.9",
        "install": "pip install -e '.[dev]'",
    }
    for k in [
        '2.18', '2.19', '2.20', '3.0', '3.1', '3.10', '3.11', '3.12',
        '3.13', '3.15', '3.16', '3.19', '3.2', '3.4', '3.8', '3.9'
    ]
}

MAP_VERSION_TO_INSTALL_PVLIB = {
    k: {
        "python": "3.9",
        "install": "pip install -e .[all]",
        "packages": "pandas scipy",
        "pip_packages": "jupyter ipython matplotlib pytest flake8"
    }
    for k in [
        '0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9'
    ]
}

MAP_VERSION_TO_INSTALL_PYDICOM = {
    k: {
        "python": "3.6",
        "install": "pip install -e .",
        "packages": "numpy"
    }
    for k in [
        '1.0', '1.1', '1.2', '1.3', '1.4',
        '2.0', '2.1', '2.2', '2.3', '2.4', '3.0'
    ]
}
MAP_VERSION_TO_INSTALL_PYDICOM.update({
    k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.8"}
    for k in ['1.4', '2.0']})
MAP_VERSION_TO_INSTALL_PYDICOM.update({
    k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.9"}
    for k in ['2.1', '2.2']})
MAP_VERSION_TO_INSTALL_PYDICOM.update({
    k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.10"}
    for k in ['2.3']})
MAP_VERSION_TO_INSTALL_PYDICOM.update({
    k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.11"}
    for k in ['2.4', '3.0']})

MAP_VERSION_TO_INSTALL_HUMANEVAL= {k: { "python": "3.9" } for k in ['1.0']}

# Constants - Task Instance Instllation Environment
MAP_VERSION_TO_INSTALL = {
    "astropy/astropy": MAP_VERSION_TO_INSTALL_ASTROPY,
    "dbt-labs/dbt-core": MAP_VERSION_TO_INSTALL_DBT_CORE,
    "django/django": MAP_VERSION_TO_INSTALL_DJANGO,
    "huggingface/transformers": MAP_VERSION_TO_INSTALL_TRANSFORMERS,
    "matplotlib/matplotlib": MAP_VERSION_TO_INSTALL_MATPLOTLIB,
    "marshmallow-code/marshmallow": MAP_VERSION_TO_INSTALL_MARSHMALLOW,
    "mwaskom/seaborn": MAP_VERSION_TO_INSTALL_SEABORN,
    "pallets/flask": MAP_VERSION_TO_INSTALL_FLASK,
    "psf/requests": MAP_VERSION_TO_INSTALL_REQUESTS,
    "pvlib/pvlib-python": MAP_VERSION_TO_INSTALL_PVLIB,
    "pydata/xarray": MAP_VERSION_TO_INSTALL_XARRAY,
    "pydicom/pydicom": MAP_VERSION_TO_INSTALL_PYDICOM,
    "pylint-dev/astroid": MAP_VERSION_TO_INSTALL_ASTROID,
    "pylint-dev/pylint": MAP_VERSION_TO_INSTALL_PYLINT,
    "pytest-dev/pytest": MAP_VERSION_TO_INSTALL_PYTEST,
    "pyvista/pyvista": MAP_VERSION_TO_INSTALL_PYVISTA,
    "scikit-learn/scikit-learn": MAP_VERSION_TO_INSTALL_SKLEARN,
    "sphinx-doc/sphinx": MAP_VERSION_TO_INSTALL_SPHINX,
    "sqlfluff/sqlfluff": MAP_VERSION_TO_INSTALL_SQLFLUFF,
    "swe-bench/humaneval": MAP_VERSION_TO_INSTALL_HUMANEVAL,
    "sympy/sympy": MAP_VERSION_TO_INSTALL_SYMPY,
}

# Constants - Repository Specific Installation Instructions
MAP_REPO_TO_INSTALL = {}

# Constants - Task Instance Test Frameworks
TEST_PYTEST = "pytest --no-header -rA --tb=no -p no:cacheprovider"
MAP_REPO_TO_TEST_FRAMEWORK = {
    "astropy/astropy": TEST_PYTEST,
    "dbt-labs/dbt-core": TEST_PYTEST,
    "django/django": "./tests/runtests.py --verbosity 2",
    "huggingface/transformers": TEST_PYTEST,
    "marshmallow-code/marshmallow": TEST_PYTEST,
    "matplotlib/matplotlib": TEST_PYTEST,
    "mwaskom/seaborn": "pytest --no-header -rA",
    "pallets/flask": TEST_PYTEST,
    "psf/requests": TEST_PYTEST,
    "pvlib/pvlib-python": TEST_PYTEST,
    "pydata/xarray": TEST_PYTEST,
    "pydicom/pydicom": TEST_PYTEST,
    "pylint-dev/astroid": TEST_PYTEST,
    "pylint-dev/pylint": TEST_PYTEST,
    "pytest-dev/pytest": "pytest -rA",
    "pyvista/pyvista": TEST_PYTEST,
    "scikit-learn/scikit-learn": TEST_PYTEST,
    "sphinx-doc/sphinx": "tox -epy39 -v --",
    "sqlfluff/sqlfluff": TEST_PYTEST,
    "swe-bench/humaneval": "python",
    "sympy/sympy": "bin/test -C --verbose",
}

# Constants - Task Instance Requirements File Paths
MAP_REPO_TO_REQS_PATHS = {
    "dbt-labs/dbt-core": ["dev-requirements.txt", "dev_requirements.txt"],
    "django/django": ["tests/requirements/py3.txt"],
    "matplotlib/matplotlib": ["requirements/dev/dev-requirements.txt", "requirements/testing/travis_all.txt"],
    "pallets/flask": ["requirements/dev.txt"],
    "pylint-dev/pylint": ["requirements_test.txt"],
    "pyvista/pyvista": ["requirements_test.txt", 'requirements.txt'],
    "sqlfluff/sqlfluff": ["requirements_dev.txt"],
    "sympy/sympy": ["requirements-dev.txt"],
}

# Constants - Task Instance environment.yml File Paths
MAP_REPO_TO_ENV_YML_PATHS = {
    "matplotlib/matplotlib": ["environment.yml"],
    "pydata/xarray": ["ci/requirements/environment.yml", "environment.yml"],
}

# Constants - Evaluation Keys
KEY_INSTANCE_ID = "instance_id"
KEY_MODEL = "model_name_or_path"
KEY_PREDICTION = "model_patch"

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

# Constants - Repo/Version Mapped to Appropriate Conda Link
MAP_REPO_VERSION_TO_CONDA_LINK = {
    "django/django": {
        "1.11": "py311_23.9.0-0",
    },
    "matplotlib/matplotlib": {
        "3.1": "py311_23.9.0-0",
        "3.2": "py311_23.9.0-0",
        "3.3": "py311_23.9.0-0",
        "3.4": "py311_23.9.0-0",
        "3.0": "py311_23.10.0-1",
    },
    "sympy/sympy": {
        "1.0": "py39_23.9.0-0",
    },
}

DEFAULT_CONDA_LINK = "py39_23.10.0-1"
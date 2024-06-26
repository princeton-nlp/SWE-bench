from enum import Enum
from typing import TypedDict


class SWEbenchInstance(TypedDict):
    repo: str
    instance_id: str
    base_commit: str
    patch: str
    test_patch: str
    problem_statement: str
    hints_text: str
    created_at: str
    version: str
    FAIL_TO_PASS: str
    PASS_TO_PASS: str
    environment_setup_commit: str


MAP_VERSION_TO_INSTALL_SKLEARN = {
    k: {
        "python": "3.6",
        "packages": "numpy scipy cython pytest pandas matplotlib",
        "install": "python -m pip install -v --no-use-pep517 --no-build-isolation -e .",
        "pip_packages": [
            "cython",
            "numpy==1.19.2",
            "setuptools",
            "scipy==1.5.2",
        ],
    }
    for k in ["0.20", "0.21", "0.22"]
}
MAP_VERSION_TO_INSTALL_SKLEARN.update(
    {
        k: {
            "python": "3.9",
            "packages": "numpy scipy cython setuptools pytest pandas matplotlib joblib threadpoolctl",
            "install": "python -m pip install -v --no-use-pep517 --no-build-isolation -e .",
            "pip_packages": ["cython", "setuptools", "numpy", "scipy"],
        }
        for k in ["1.3", "1.4"]
    }
)
MAP_VERSION_TO_INSTALL_FLASK = {
    "2.0": {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "python -m pip install -e .",
        "pip_packages": [
            "Werkzeug==2.3.7",
            "Jinja2==3.0.1",
            "itsdangerous==2.1.2",
            "click==8.0.1",
            "MarkupSafe==2.1.3",
        ],
    },
    "2.1": {
        "python": "3.10",
        "packages": "requirements.txt",
        "install": "python -m pip install -e .",
        "pip_packages": [
            "click==8.1.3",
            "itsdangerous==2.1.2",
            "Jinja2==3.1.2",
            "MarkupSafe==2.1.1",
            "Werkzeug==2.3.7",
        ],
    },
}
MAP_VERSION_TO_INSTALL_FLASK.update(
    {
        k: {
            "python": "3.11",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
            "pip_packages": [
                "click==8.1.3",
                "itsdangerous==2.1.2",
                "Jinja2==3.1.2",
                "MarkupSafe==2.1.1",
                "Werkzeug==2.3.7",
            ],
        }
        for k in ["2.2", "2.3"]
    }
)
MAP_VERSION_TO_INSTALL_DJANGO = {
    k: {
        "python": "3.5",
        "packages": "requirements.txt",
        "pre_install": [
            "apt-get update && apt-get install -y locales",
            "echo 'en_US UTF-8' > /etc/locale.gen",
            "locale-gen en_US.UTF-8",
        ],
        "install": "python setup.py install",
        "pip_packages": ["setuptools"],
        "eval_commands": [
            "export LANG=en_US.UTF-8",
            "export LC_ALL=en_US.UTF-8",
            "export PYTHONIOENCODING=utf8",
            "export LANGUAGE=en_US:en",
        ],
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
            "eval_commands": [
                "sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen",
                "export LANG=en_US.UTF-8",
                "export LANGUAGE=en_US:en",
                "export LC_ALL=en_US.UTF-8",
            ],
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
    for k in ["0.7", "0.8", "0.9", "0.11", "0.13", "0.14", "1.1", "1.2", "2.0", "2.2"]
    + ["2.3", "2.4", "2.5", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12", "2.17"]
    + ["2.18", "2.19", "2.22", "2.26", "2.25", "2.27", "3.0"]
}
MAP_VERSION_TO_INSTALL_SEABORN = {
    k: {
        "python": "3.9",
        "install": "python -m pip install -e .",
        "pip_packages": [
            "contourpy==1.1.0",
            "cycler==0.11.0",
            "fonttools==4.42.1",
            "importlib-resources==6.0.1",
            "kiwisolver==1.4.5",
            "matplotlib==3.7.2",
            "numpy==1.25.2",
            "packaging==23.1",
            "pandas==1.3.5",  # 2.0.3
            "pillow==10.0.0",
            "pyparsing==3.0.9",
            "pytest",
            "python-dateutil==2.8.2",
            "pytz==2023.3.post1",
            "scipy==1.11.2",
            "six==1.16.0",
            "tzdata==2023.1",
            "zipp==3.16.2",
        ],
    }
    for k in ["0.11"]
}
MAP_VERSION_TO_INSTALL_SEABORN.update(
    {
        k: {
            "python": "3.9",
            "install": "python -m pip install -e .[dev]",
            "pip_packages": [
                "contourpy==1.1.0",
                "cycler==0.11.0",
                "fonttools==4.42.1",
                "importlib-resources==6.0.1",
                "kiwisolver==1.4.5",
                "matplotlib==3.7.2",
                "numpy==1.25.2",
                "packaging==23.1",
                "pandas==2.0.0",
                "pillow==10.0.0",
                "pyparsing==3.0.9",
                "pytest",
                "python-dateutil==2.8.2",
                "pytz==2023.3.post1",
                "scipy==1.11.2",
                "six==1.16.0",
                "tzdata==2023.1",
                "zipp==3.16.2",
            ],
        }
        for k in ["0.12", "0.13"]
    }
)
MAP_VERSION_TO_INSTALL_PYTEST = {
    k: {"python": "3.9", "install": "python -m pip install -e ."}
    for k in [
        "4.4",
        "4.5",
        "4.6",
        "5.0",
        "5.1",
        "5.2",
        "5.3",
        "5.4",
        "6.0",
        "6.2",
        "6.3",
        "7.0",
        "7.1",
        "7.2",
        "7.4",
        "8.0",
    ]
}
MAP_VERSION_TO_INSTALL_PYTEST["4.4"]["pip_packages"] = [
    "atomicwrites==1.4.1",
    "attrs==23.1.0",
    "more-itertools==10.1.0",
    "pluggy==0.13.1",
    "py==1.11.0",
    "setuptools==68.0.0",
    "six==1.16.0",
]
MAP_VERSION_TO_INSTALL_PYTEST["4.5"]["pip_packages"] = [
    "atomicwrites==1.4.1",
    "attrs==23.1.0",
    "more-itertools==10.1.0",
    "pluggy==0.11.0",
    "py==1.11.0",
    "setuptools==68.0.0",
    "six==1.16.0",
    "wcwidth==0.2.6",
]
MAP_VERSION_TO_INSTALL_PYTEST["4.6"]["pip_packages"] = [
    "atomicwrites==1.4.1",
    "attrs==23.1.0",
    "more-itertools==10.1.0",
    "packaging==23.1",
    "pluggy==0.13.1",
    "py==1.11.0",
    "six==1.16.0",
    "wcwidth==0.2.6",
]
for k in ["5.0", "5.1", "5.2"]:
    MAP_VERSION_TO_INSTALL_PYTEST[k]["pip_packages"] = [
        "atomicwrites==1.4.1",
        "attrs==23.1.0",
        "more-itertools==10.1.0",
        "packaging==23.1",
        "pluggy==0.13.1",
        "py==1.11.0",
        "wcwidth==0.2.6",
    ]
MAP_VERSION_TO_INSTALL_PYTEST["5.3"]["pip_packages"] = [
    "attrs==23.1.0",
    "more-itertools==10.1.0",
    "packaging==23.1",
    "pluggy==0.13.1",
    "py==1.11.0",
    "wcwidth==0.2.6",
]
MAP_VERSION_TO_INSTALL_PYTEST["5.4"]["pip_packages"] = [
    "py==1.11.0",
    "packaging==23.1",
    "attrs==23.1.0",
    "more-itertools==10.1.0",
    "pluggy==0.13.1",
]
MAP_VERSION_TO_INSTALL_PYTEST["6.0"]["pip_packages"] = [
    "attrs==23.1.0",
    "iniconfig==2.0.0",
    "more-itertools==10.1.0",
    "packaging==23.1",
    "pluggy==0.13.1",
    "py==1.11.0",
    "toml==0.10.2",
]
for k in ["6.2", "6.3"]:
    MAP_VERSION_TO_INSTALL_PYTEST[k]["pip_packages"] = [
        "attrs==23.1.0",
        "iniconfig==2.0.0",
        "packaging==23.1",
        "pluggy==0.13.1",
        "py==1.11.0",
        "toml==0.10.2",
    ]
MAP_VERSION_TO_INSTALL_PYTEST["7.0"]["pip_packages"] = [
    "attrs==23.1.0",
    "iniconfig==2.0.0",
    "packaging==23.1",
    "pluggy==0.13.1",
    "py==1.11.0",
]
for k in ["7.1", "7.2"]:
    MAP_VERSION_TO_INSTALL_PYTEST[k]["pip_packages"] = [
        "attrs==23.1.0",
        "iniconfig==2.0.0",
        "packaging==23.1",
        "pluggy==0.13.1",
        "py==1.11.0",
        "tomli==2.0.1",
    ]
MAP_VERSION_TO_INSTALL_PYTEST["7.4"]["pip_packages"] = [
    "iniconfig==2.0.0",
    "packaging==23.1",
    "pluggy==1.3.0",
    "exceptiongroup==1.1.3",
    "tomli==2.0.1",
]
MAP_VERSION_TO_INSTALL_PYTEST["8.0"]["pip_packages"] = [
    "iniconfig==2.0.0",
    "packaging==23.1",
    "pluggy==1.3.0",
    "exceptiongroup==1.1.3",
    "tomli==2.0.1",
]
MAP_VERSION_TO_INSTALL_MATPLOTLIB = {
    k: {
        "python": "3.11",
        "packages": "environment.yml",
        "install": "python -m pip install -e .",
        "pre_install": [
            "apt-get -y update && apt-get -y upgrade && apt-get install -y imagemagick ffmpeg texlive texlive-latex-extra texlive-fonts-recommended texlive-xetex texlive-luatex cm-super dvipng"
        ],
        "pip_packages": [
            "contourpy==1.1.0",
            "cycler==0.11.0",
            "fonttools==4.42.1",
            "ghostscript",
            "kiwisolver==1.4.5",
            "numpy==1.25.2",
            "packaging==23.1",
            "pillow==10.0.0",
            "pikepdf",
            "pyparsing==3.0.9",
            "python-dateutil==2.8.2",
            "six==1.16.0",
            "setuptools==68.1.2",
            "setuptools-scm==7.1.0",
            "typing-extensions==4.7.1",
        ],
    }
    for k in ["3.5", "3.6", "3.7"]
}
MAP_VERSION_TO_INSTALL_MATPLOTLIB.update(
    {
        k: {
            "python": "3.8",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
            "pre_install": [
                "apt-get -y update && apt-get -y upgrade && apt-get install -y imagemagick ffmpeg libfreetype6-dev pkg-config texlive texlive-latex-extra texlive-fonts-recommended texlive-xetex texlive-luatex cm-super"
            ],
            "pip_packages": ["pytest", "ipython"],
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
            "pre_install": [
                "apt-get -y update && apt-get -y upgrade && apt-get install -y imagemagick ffmpeg libfreetype6-dev pkg-config"
            ],
            "pip_packages": ["pytest"],
        }
        for k in ["3.0"]
    }
)
MAP_VERSION_TO_INSTALL_MATPLOTLIB.update(
    {
        k: {
            "python": "3.5",
            "install": "python setup.py build; python setup.py install",
            "pre_install": [
                "apt-get -y update && apt-get -y upgrade && && apt-get install -y imagemagick ffmpeg"
            ],
            "pip_packages": ["pytest"],
            "execute_test_as_nonroot": True,
        }
        for k in ["2.0", "2.1", "2.2", "1.0", "1.1", "1.2", "1.3", "1.4", "1.5"]
    }
)
MAP_VERSION_TO_INSTALL_SPHINX = {
    k: {
        "python": "3.9",
        "pip_packages": ["tox"],
        "install": "python -m pip install -e .[test]",
        "pre_install": ["sed -i 's/pytest/pytest -rA/' tox.ini"],
    }
    for k in ["1.5", "1.6", "1.7", "1.8", "2.0", "2.1", "2.2", "2.3", "2.4", "3.0"]
    + ["3.1", "3.2", "3.3", "3.4", "3.5", "4.0", "4.1", "4.2", "4.3", "4.4"]
    + ["4.5", "5.0", "5.1", "5.2", "5.3", "6.0", "6.2", "7.0", "7.1", "7.2"]
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
MAP_VERSION_TO_INSTALL_SPHINX["7.2"]["pre_install"] += [
    "apt-get update && apt-get install -y graphviz"
]
MAP_VERSION_TO_INSTALL_ASTROPY = {
    k: {
        "python": "3.9",
        "install": "python -m pip install -e .[test] --verbose",
        "pip_packages": [
            "attrs==23.1.0",
            "exceptiongroup==1.1.3",
            "execnet==2.0.2",
            "hypothesis==6.82.6",
            "iniconfig==2.0.0",
            "numpy==1.25.2",
            "packaging==23.1",
            "pluggy==1.3.0",
            "psutil==5.9.5",
            "pyerfa==2.0.0.3",
            "pytest-arraydiff==0.5.0",
            "pytest-astropy-header==0.2.2",
            "pytest-astropy==0.10.0",
            "pytest-cov==4.1.0",
            "pytest-doctestplus==1.0.0",
            "pytest-filter-subpackage==0.1.2",
            "pytest-mock==3.11.1",
            "pytest-openfiles==0.5.0",
            "pytest-remotedata==0.4.0",
            "pytest-xdist==3.3.1",
            "pytest==7.4.0",
            "PyYAML==6.0.1",
            "setuptools==68.0.0",
            "sortedcontainers==2.4.0",
            "tomli==2.0.1",
        ],
    }
    for k in ["0.1", "0.2", "0.3", "0.4", "1.1", "1.2", "1.3", "3.0", "3.1", "3.2"]
    + ["4.1", "4.2", "4.3", "5.0", "5.1", "5.2"]
}
for k in ["4.1", "4.2", "4.3", "5.0", "5.1", "5.2"]:
    MAP_VERSION_TO_INSTALL_ASTROPY[k]["pre_install"] = [
        'sed -i \'s/requires = \\["setuptools",/requires = \\["setuptools==68.0.0",/\' pyproject.toml'
    ]
MAP_VERSION_TO_INSTALL_SYMPY = {
    k: {
        "python": "3.9",
        "packages": "mpmath flake8",
        "pip_packages": ["mpmath==1.3.0", "flake8-comprehensions"],
        "install": "python -m pip install -e .",
    }
    for k in ["0.7", "1.0", "1.1", "1.10", "1.11", "1.12", "1.2", "1.4", "1.5", "1.6"]
    + ["1.7", "1.8", "1.9"]
}
MAP_VERSION_TO_INSTALL_SYMPY.update(
    {
        k: {
            "python": "3.9",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
            "pip_packages": ["mpmath==1.3.0"],
        }
        for k in ["1.13"]
    }
)
MAP_VERSION_TO_INSTALL_PYLINT = {
    k: {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "python -m pip install -e .",
    }
    for k in [
        "2.10",
        "2.11",
        "2.13",
        "2.14",
        "2.15",
        "2.16",
        "2.17",
        "2.8",
        "2.9",
        "3.0",
    ]
}
MAP_VERSION_TO_INSTALL_PYLINT["2.8"]["pip_packages"] = ["pyenchant==3.2"]
MAP_VERSION_TO_INSTALL_PYLINT["2.8"]["pre_install"] = [
    "apt-get update && apt-get install -y libenchant-2-dev hunspell-en-us"
]
MAP_VERSION_TO_INSTALL_PYLINT.update(
    {
        k: {
            **MAP_VERSION_TO_INSTALL_PYLINT[k],
            "pip_packages": ["astroid==3.0.0a6", "setuptools"],
        }
        for k in ["3.0"]
    }
)
for v in ["2.14", "2.15", "2.17", "3.0"]:
    MAP_VERSION_TO_INSTALL_PYLINT[v]["nano_cpus"] = int(2e9)

MAP_VERSION_TO_INSTALL_XARRAY = {
    k: {
        "python": "3.10",
        "packages": "environment.yml",
        "install": "python -m pip install -e .",
        "pip_packages": [
            "numpy==1.23.0",
            "packaging==23.1",
            "pandas==1.5.3",
            "pytest==7.4.0",
            "python-dateutil==2.8.2",
            "pytz==2023.3",
            "six==1.16.0",
            "scipy==1.11.1",
            "setuptools==68.0.0"
        ],
        "no_use_env": True,
    }
    for k in ["0.12", "0.18", "0.19", "0.20", "2022.03", "2022.06", "2022.09"]
}

MAP_VERSION_TO_INSTALL_SQLFLUFF = {
    k: {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "python -m pip install -e .",
    }
    for k in [
        "0.10",
        "0.11",
        "0.12",
        "0.13",
        "0.4",
        "0.5",
        "0.6",
        "0.8",
        "0.9",
        "1.0",
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "2.0",
        "2.1",
        "2.2",
    ]
}
MAP_VERSION_TO_INSTALL_DBT_CORE = {
    k: {
        "python": "3.9",
        "packages": "requirements.txt",
        "install": "python -m pip install -e .",
    }
    for k in [
        "0.13",
        "0.14",
        "0.15",
        "0.16",
        "0.17",
        "0.18",
        "0.19",
        "0.20",
        "0.21",
        "1.0",
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "1.6",
        "1.7",
    ]
}
MAP_VERSION_TO_INSTALL_PYVISTA = {
    k: {
        "python": "3.9",
        "install": "python -m pip install -e .",
        "pip_packages": ["pytest"],
    }
    for k in ["0.20", "0.21", "0.22", "0.23"]
}
MAP_VERSION_TO_INSTALL_PYVISTA.update(
    {
        k: {
            "python": "3.9",
            "packages": "requirements.txt",
            "install": "python -m pip install -e .",
            "pip_packages": ["pytest"],
        }
        for k in [
            "0.24",
            "0.25",
            "0.26",
            "0.27",
            "0.28",
            "0.29",
            "0.30",
            "0.31",
            "0.32",
            "0.33",
            "0.34",
            "0.35",
            "0.36",
            "0.37",
            "0.38",
            "0.39",
            "0.40",
            "0.41",
            "0.42",
            "0.43",
        ]
    }
)
MAP_VERSION_TO_INSTALL_ASTROID = {
    k: {
        "python": "3.9",
        "install": "python -m pip install -e .",
        "pip_packages": ["pytest"],
    }
    for k in [
        "2.10",
        "2.12",
        "2.13",
        "2.14",
        "2.15",
        "2.16",
        "2.5",
        "2.6",
        "2.7",
        "2.8",
        "2.9",
        "3.0",
    ]
}
MAP_VERSION_TO_INSTALL_MARSHMALLOW = {
    k: {
        "python": "3.9",
        "install": "python -m pip install -e '.[dev]'",
    }
    for k in [
        "2.18",
        "2.19",
        "2.20",
        "3.0",
        "3.1",
        "3.10",
        "3.11",
        "3.12",
        "3.13",
        "3.15",
        "3.16",
        "3.19",
        "3.2",
        "3.4",
        "3.8",
        "3.9",
    ]
}
MAP_VERSION_TO_INSTALL_PVLIB = {
    k: {
        "python": "3.9",
        "install": "python -m pip install -e .[all]",
        "packages": "pandas scipy",
        "pip_packages": ["jupyter", "ipython", "matplotlib", "pytest", "flake8"],
    }
    for k in ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]
}
MAP_VERSION_TO_INSTALL_PYDICOM = {
    k: {"python": "3.6", "install": "python -m pip install -e .", "packages": "numpy"}
    for k in [
        "1.0",
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "2.0",
        "2.1",
        "2.2",
        "2.3",
        "2.4",
        "3.0",
    ]
}
MAP_VERSION_TO_INSTALL_PYDICOM.update(
    {k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.8"} for k in ["1.4", "2.0"]}
)
MAP_VERSION_TO_INSTALL_PYDICOM.update(
    {k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.9"} for k in ["2.1", "2.2"]}
)
MAP_VERSION_TO_INSTALL_PYDICOM.update(
    {k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.10"} for k in ["2.3"]}
)
MAP_VERSION_TO_INSTALL_PYDICOM.update(
    {k: {**MAP_VERSION_TO_INSTALL_PYDICOM[k], "python": "3.11"} for k in ["2.4", "3.0"]}
)
MAP_VERSION_TO_INSTALL_HUMANEVAL = {k: {"python": "3.9"} for k in ["1.0"]}

# Constants - Task Instance Instllation Environment
MAP_VERSION_TO_INSTALL = {
    "astropy/astropy": MAP_VERSION_TO_INSTALL_ASTROPY,
    "dbt-labs/dbt-core": MAP_VERSION_TO_INSTALL_DBT_CORE,
    "django/django": MAP_VERSION_TO_INSTALL_DJANGO,
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
    "astropy/astropy": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_ASTROPY.keys()},
    "django/django": {
        k: "./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1"
        for k in MAP_VERSION_TO_INSTALL_DJANGO.keys()
    },
    "marshmallow-code/marshmallow": {
        k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_MARSHMALLOW.keys()
    },
    "matplotlib/matplotlib": {
        k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_MATPLOTLIB.keys()
    },
    "mwaskom/seaborn": {
        k: "pytest --no-header -rA" for k in MAP_VERSION_TO_INSTALL_SEABORN.keys()
    },
    "pallets/flask": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_FLASK.keys()},
    "psf/requests": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_REQUESTS.keys()},
    "pvlib/pvlib-python": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_PVLIB.keys()},
    "pydata/xarray": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_XARRAY.keys()},
    "pydicom/pydicom": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_PYDICOM.keys()},
    "pylint-dev/astroid": {
        k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_ASTROID.keys()
    },
    "pylint-dev/pylint": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_PYLINT.keys()},
    "pytest-dev/pytest": {
        k: "pytest -rA" for k in MAP_VERSION_TO_INSTALL_PYTEST.keys()
    },
    "pyvista/pyvista": {k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_PYVISTA.keys()},
    "scikit-learn/scikit-learn": {
        k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_SKLEARN.keys()
    },
    "sphinx-doc/sphinx": {
        k: "tox -epy39 -v --" for k in MAP_VERSION_TO_INSTALL_SPHINX.keys()
    },
    "sqlfluff/sqlfluff": {
        k: TEST_PYTEST for k in MAP_VERSION_TO_INSTALL_SQLFLUFF.keys()
    },
    "swe-bench/humaneval": {
        k: "python" for k in MAP_VERSION_TO_INSTALL_HUMANEVAL.keys()
    },
    "sympy/sympy": {
        k: "PYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' bin/test -C --verbose"
        for k in MAP_VERSION_TO_INSTALL_SYMPY.keys()
    },
}
MAP_REPO_TO_TEST_FRAMEWORK["django/django"]["1.9"] = "./tests/runtests.py --verbosity 2"

TEST_PYTEST_VERBOSE = "pytest -rA --tb=long -p no:cacheprovider"
MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE = {
    "astropy/astropy": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_ASTROPY.keys()
    },
    "django/django": {
        k: "./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1"
        for k in MAP_VERSION_TO_INSTALL_DJANGO.keys()
    },
    "marshmallow-code/marshmallow": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_MARSHMALLOW.keys()
    },
    "matplotlib/matplotlib": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_MATPLOTLIB.keys()
    },
    "mwaskom/seaborn": {
        k: "pytest -rA --tb=long" for k in MAP_VERSION_TO_INSTALL_SEABORN.keys()
    },
    "pallets/flask": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_FLASK.keys()
    },
    "psf/requests": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_REQUESTS.keys()
    },
    "pvlib/pvlib-python": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_PVLIB.keys()
    },
    "pydata/xarray": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_XARRAY.keys()
    },
    "pydicom/pydicom": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_PYDICOM.keys()
    },
    "pylint-dev/astroid": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_ASTROID.keys()
    },
    "pylint-dev/pylint": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_PYLINT.keys()
    },
    "pytest-dev/pytest": {
        k: "pytest -rA --tb=long" for k in MAP_VERSION_TO_INSTALL_PYTEST.keys()
    },
    "pyvista/pyvista": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_PYVISTA.keys()
    },
    "scikit-learn/scikit-learn": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_SKLEARN.keys()
    },
    "sphinx-doc/sphinx": {
        k: "tox -epy39 -v --" for k in MAP_VERSION_TO_INSTALL_SPHINX.keys()
    },
    "sqlfluff/sqlfluff": {
        k: TEST_PYTEST_VERBOSE for k in MAP_VERSION_TO_INSTALL_SQLFLUFF.keys()
    },
    "swe-bench/humaneval": {
        k: "python" for k in MAP_VERSION_TO_INSTALL_HUMANEVAL.keys()
    },
    "sympy/sympy": {
        k: "bin/test -C --verbose" for k in MAP_VERSION_TO_INSTALL_SYMPY.keys()
    },
}
MAP_REPO_TO_TEST_FRAMEWORK["django/django"]["1.9"] = "./tests/runtests.py --verbosity 2"

# Constants - Task Instance Requirements File Paths
MAP_REPO_TO_REQS_PATHS = {
    "dbt-labs/dbt-core": ["dev-requirements.txt", "dev_requirements.txt"],
    "django/django": ["tests/requirements/py3.txt"],
    "matplotlib/matplotlib": [
        "requirements/dev/dev-requirements.txt",
        "requirements/testing/travis_all.txt",
    ],
    "pallets/flask": ["requirements/dev.txt"],
    "pylint-dev/pylint": ["requirements_test.txt"],
    "pyvista/pyvista": ["requirements_test.txt", "requirements.txt"],
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


# Constants - Patch Types
class PatchType(Enum):
    PATCH_GOLD = "gold"
    PATCH_PRED = "pred"
    PATCH_PRED_TRY = "pred_try"
    PATCH_PRED_MINIMAL = "pred_minimal"
    PATCH_PRED_MINIMAL_TRY = "pred_minimal_try"
    PATCH_TEST = "test"

    def __str__(self):
        return self.value


# Constants - Miscellaneous
NON_TEST_EXTS = [
    ".json",
    ".png",
    "csv",
    ".txt",
    ".md",
    ".jpg",
    ".jpeg",
    ".pkl",
    ".yml",
    ".yaml",
    ".toml",
]
SWE_BENCH_URL_RAW = "https://raw.githubusercontent.com/"
USE_X86 = {
    "matplotlib__matplotlib-26278",
    "scikit-learn__scikit-learn-14898",
    "matplotlib__matplotlib-25631",
    "scikit-learn__scikit-learn-14878",
    "pydata__xarray-5455",
    "scikit-learn__scikit-learn-11160",
    "pydata__xarray-6461",
    "scikit-learn__scikit-learn-12443",
    "pydata__xarray-4827",
    "scikit-learn__scikit-learn-12462",
    "pydata__xarray-2922",
    "pydata__xarray-7019",
    "django__django-10097",
    "pydata__xarray-4182",
    "scikit-learn__scikit-learn-13283",
    "scikit-learn__scikit-learn-13620",
    "scikit-learn__scikit-learn-14732",
    "matplotlib__matplotlib-26223",
    "scikit-learn__scikit-learn-13087",
    "matplotlib__matplotlib-26341",
    "matplotlib__matplotlib-25346",
    "pydata__xarray-6938",
    "scikit-learn__scikit-learn-14764",
    "scikit-learn__scikit-learn-12973",
    "scikit-learn__scikit-learn-14092",
    "pydata__xarray-7233",
    "scikit-learn__scikit-learn-14053",
    "matplotlib__matplotlib-25859",
    "scikit-learn__scikit-learn-12983",
    "scikit-learn__scikit-learn-13241",
    "pydata__xarray-7003",
    "scikit-learn__scikit-learn-11206",
    "pydata__xarray-3305",
    "pydata__xarray-4510",
    "matplotlib__matplotlib-23740",
    "matplotlib__matplotlib-25126",
    "scikit-learn__scikit-learn-10908",
    "matplotlib__matplotlib-24265",
    "pydata__xarray-3635",
    "pydata__xarray-3114",
    "pydata__xarray-4356",
    "matplotlib__matplotlib-26101",
    "pydata__xarray-4695",
    "scikit-learn__scikit-learn-12733",
    "django__django-15682",
    "scikit-learn__scikit-learn-13497",
    "matplotlib__matplotlib-23049",
    "matplotlib__matplotlib-25052",
    "scikit-learn__scikit-learn-15120",
    "scikit-learn__scikit-learn-13485",
    "matplotlib__matplotlib-22991",
    "pydata__xarray-3976",
    "pydata__xarray-5662",
    "scikit-learn__scikit-learn-11243",
    "django__django-10213",
    "matplotlib__matplotlib-26184",
    "django__django-13431",
    "scikit-learn__scikit-learn-10508",
    "pydata__xarray-3338",
    "matplotlib__matplotlib-22865",
    "scikit-learn__scikit-learn-14067",
    "matplotlib__matplotlib-24189",
    "matplotlib__matplotlib-26078",
    "pydata__xarray-3159",
    "scikit-learn__scikit-learn-15094",
    "matplotlib__matplotlib-13983",
    "pydata__xarray-7101",
    "scikit-learn__scikit-learn-7760",
    "scikit-learn__scikit-learn-13046",
    "django__django-15474",
    "scikit-learn__scikit-learn-12557",
    "scikit-learn__scikit-learn-13124",
    "scikit-learn__scikit-learn-11281",
    "pydata__xarray-4339",
    "matplotlib__matplotlib-23987",
    "pydata__xarray-5233",
    "scikit-learn__scikit-learn-13328",
    "pydata__xarray-3993",
    "scikit-learn__scikit-learn-12583",
    "scikit-learn__scikit-learn-10297",
    "matplotlib__matplotlib-24570",
    "scikit-learn__scikit-learn-13013",
    "scikit-learn__scikit-learn-3840",
    "matplotlib__matplotlib-22767",
    "scikit-learn__scikit-learn-11596",
    "scikit-learn__scikit-learn-13253",
    "pydata__xarray-7150",
    "django__django-14164",
    "scikit-learn__scikit-learn-14430",
    "scikit-learn__scikit-learn-10558",
    "pydata__xarray-3156",
    "pydata__xarray-7112",
    "scikit-learn__scikit-learn-14894",
    "scikit-learn__scikit-learn-9939",
    "scikit-learn__scikit-learn-15100",
    "matplotlib__matplotlib-26300",
    "matplotlib__matplotlib-25565",
    "scikit-learn__scikit-learn-10577",
    "scikit-learn__scikit-learn-15086",
    "matplotlib__matplotlib-25515",
    "matplotlib__matplotlib-23562",
    "scikit-learn__scikit-learn-13454",
    "pydata__xarray-4994",
    "matplotlib__matplotlib-25433",
    "matplotlib__matplotlib-13984",
    "scikit-learn__scikit-learn-11346",
    "django__django-10301",
    "scikit-learn__scikit-learn-10949",
    "matplotlib__matplotlib-23332",
    "scikit-learn__scikit-learn-10471",
    "matplotlib__matplotlib-26232",
    "scikit-learn__scikit-learn-14629",
    "django__django-13121",
    "matplotlib__matplotlib-26479",
    "matplotlib__matplotlib-24111",
    "pydata__xarray-4683",
    "pydata__xarray-6601",
    "django__django-14170",
    "scikit-learn__scikit-learn-13549",
    "matplotlib__matplotlib-23267",
    "scikit-learn__scikit-learn-14908",
    "pydata__xarray-3631",
    "scikit-learn__scikit-learn-11585",
    "pydata__xarray-6386",
    "matplotlib__matplotlib-23047",
    "matplotlib__matplotlib-23088",
    "scikit-learn__scikit-learn-11496",
    "scikit-learn__scikit-learn-14869",
    "pydata__xarray-4442",
    "matplotlib__matplotlib-23266",
    "scikit-learn__scikit-learn-10443",
    "scikit-learn__scikit-learn-12471",
    "pydata__xarray-6548",
    "scikit-learn__scikit-learn-13165",
    "pydata__xarray-7147",
    "pydata__xarray-4629",
    "scikit-learn__scikit-learn-14458",
    "scikit-learn__scikit-learn-11042",
    "matplotlib__matplotlib-24971",
    "scikit-learn__scikit-learn-13496",
    "scikit-learn__scikit-learn-14544",
    "django__django-9703",
    "scikit-learn__scikit-learn-13554",
    "pydata__xarray-7052",
    "pydata__xarray-3979",
    "matplotlib__matplotlib-23913",
    "matplotlib__matplotlib-22711",
    "matplotlib__matplotlib-25785",
    "matplotlib__matplotlib-24177",
    "matplotlib__matplotlib-26208",
    "django__django-15781",
    "scikit-learn__scikit-learn-10870",
    "matplotlib__matplotlib-13989",
    "matplotlib__matplotlib-23111",
    "pydata__xarray-3677",
    "matplotlib__matplotlib-24088",
    "scikit-learn__scikit-learn-10986",
    "matplotlib__matplotlib-26011",
    "sympy__sympy-12812",
    "scikit-learn__scikit-learn-13313",
    "scikit-learn__scikit-learn-15028",
    "matplotlib__matplotlib-22734",
    "scikit-learn__scikit-learn-10777",
    "matplotlib__matplotlib-25498",
    "scikit-learn__scikit-learn-12625",
    "scikit-learn__scikit-learn-13157",
    "scikit-learn__scikit-learn-12938",
    "django__django-15180",
    "matplotlib__matplotlib-25794",
    "pydata__xarray-6889",
    "scikit-learn__scikit-learn-13280",
    "pydata__xarray-3151",
    "matplotlib__matplotlib-25772",
    "matplotlib__matplotlib-22871",
    "matplotlib__matplotlib-23412",
    "pydata__xarray-5131",
    "scikit-learn__scikit-learn-13864",
    "scikit-learn__scikit-learn-11310",
    "django__django-10316",
    "pydata__xarray-6599",
    "django__django-14155",
    "pydata__xarray-3905",
    "pydata__xarray-7089",
    "matplotlib__matplotlib-23742",
    "scikit-learn__scikit-learn-13877",
    "astropy__astropy-7973",
    "scikit-learn__scikit-learn-15524",
    "matplotlib__matplotlib-23299",
    "pydata__xarray-2905",
    "matplotlib__matplotlib-24431",
    "matplotlib__matplotlib-24026",
    "pydata__xarray-6992",
    "scikit-learn__scikit-learn-12486",
    "scikit-learn__scikit-learn-14087",
    "django__django-15698",
    "matplotlib__matplotlib-26285",
    "scikit-learn__scikit-learn-13618",
    "scikit-learn__scikit-learn-10881",
    "scikit-learn__scikit-learn-14012",
    "scikit-learn__scikit-learn-14464",
    "scikit-learn__scikit-learn-12585",
    "pydata__xarray-7105",
    "matplotlib__matplotlib-24912",
    "pydata__xarray-6857",
    "django__django-13447",
    "matplotlib__matplotlib-22926",
    "scikit-learn__scikit-learn-13221",
    "matplotlib__matplotlib-23288",
    "pydata__xarray-4966",
    "pydata__xarray-7400",
    "matplotlib__matplotlib-14471",
    "matplotlib__matplotlib-24627",
    "matplotlib__matplotlib-22719",
    "matplotlib__matplotlib-25712",
    "matplotlib__matplotlib-26020",
    "pydata__xarray-3527",
    "scikit-learn__scikit-learn-9288",
    "pydata__xarray-6400",
    "scikit-learn__scikit-learn-14890",
    "scikit-learn__scikit-learn-13467",
    "scikit-learn__scikit-learn-11151",
    "django__django-9871",
    "pydata__xarray-3649",
    "pydata__xarray-5580",
    "matplotlib__matplotlib-26311",
    "pydata__xarray-4184",
    "matplotlib__matplotlib-25640",
    "matplotlib__matplotlib-25122",
    "pydata__xarray-7179",
    "pydata__xarray-4684",
    "matplotlib__matplotlib-26532",
    "sphinx-doc__sphinx-7910",
    "pydata__xarray-3239",
    "scikit-learn__scikit-learn-15119",
    "django__django-5158",
    "matplotlib__matplotlib-25667",
    "scikit-learn__scikit-learn-13584",
    "matplotlib__matplotlib-26469",
    "django__django-15292",
    "django__django-15280",
    "scikit-learn__scikit-learn-10495",
    "scikit-learn__scikit-learn-14710",
    "matplotlib__matplotlib-24604",
    "scikit-learn__scikit-learn-12656",
    "scikit-learn__scikit-learn-12827",
    "pydata__xarray-4750",
    "pydata__xarray-4911",
    "pydata__xarray-7347",
    "pydata__xarray-3406",
    "scikit-learn__scikit-learn-15393",
    "django__django-13417",
    "scikit-learn__scikit-learn-10427",
    "scikit-learn__scikit-learn-14706",
    "matplotlib__matplotlib-24749",
    "matplotlib__matplotlib-25547",
    "matplotlib__matplotlib-23140",
    "pydata__xarray-4687",
    "matplotlib__matplotlib-22945",
    "matplotlib__matplotlib-26342",
    "pydata__xarray-4758",
    "django__django-14169",
    "matplotlib__matplotlib-24924",
    "matplotlib__matplotlib-24538",
    "scikit-learn__scikit-learn-10459",
    "pydata__xarray-5682",
    "scikit-learn__scikit-learn-12784",
    "scikit-learn__scikit-learn-13010",
    "scikit-learn__scikit-learn-11040",
    "matplotlib__matplotlib-25311",
    "scikit-learn__scikit-learn-13974",
    "scikit-learn__scikit-learn-12704",
    "scikit-learn__scikit-learn-12758",
    "scikit-learn__scikit-learn-13933",
    "django__django-12185",
    "scikit-learn__scikit-learn-10913",
    "django__django-15925",
    "matplotlib__matplotlib-25238",
    "matplotlib__matplotlib-25624",
    "django__django-10426",
    "matplotlib__matplotlib-25960",
    "pydata__xarray-4802",
    "scikit-learn__scikit-learn-15512",
    "matplotlib__matplotlib-24970",
    "scikit-learn__scikit-learn-13780",
    "matplotlib__matplotlib-26399",
    "matplotlib__matplotlib-25340",
    "matplotlib__matplotlib-25281",
    "scikit-learn__scikit-learn-13368",
    "django__django-7188",
    "matplotlib__matplotlib-23516",
    "pydata__xarray-7391",
    "pydata__xarray-6135",
    "pydata__xarray-6882",
    "scikit-learn__scikit-learn-14237",
    "pydata__xarray-5362",
    "pydata__xarray-7203",
    "scikit-learn__scikit-learn-14999",
    "scikit-learn__scikit-learn-13536",
    "matplotlib__matplotlib-23198",
    "matplotlib__matplotlib-22929",
    "scikit-learn__scikit-learn-14309",
    "scikit-learn__scikit-learn-12961",
    "scikit-learn__scikit-learn-12626",
    "django__django-15930",
    "matplotlib__matplotlib-25499",
    "matplotlib__matplotlib-25442",
    "scikit-learn__scikit-learn-11635",
    "pydata__xarray-5033",
    "scikit-learn__scikit-learn-13779",
    "pydata__xarray-6971",
    "matplotlib__matplotlib-24870",
    "scikit-learn__scikit-learn-13983",
    "scikit-learn__scikit-learn-15495",
    "pydata__xarray-4940",
    "django__django-11383",
    "matplotlib__matplotlib-25334",
    "pydata__xarray-6804",
    "matplotlib__matplotlib-24849",
    "django__django-10087",
    "django__django-15695",
    "matplotlib__matplotlib-23203",
    "pydata__xarray-7229",
    "pydata__xarray-5180",
    "scikit-learn__scikit-learn-10899",
    "scikit-learn__scikit-learn-14114",
    "scikit-learn__scikit-learn-13135",
    "pydata__xarray-4819",
    "pydata__xarray-6798",
    "django__django-15199",
    "matplotlib__matplotlib-25430",
    "scikit-learn__scikit-learn-14591",
    "scikit-learn__scikit-learn-13910",
    "matplotlib__matplotlib-25775",
    "matplotlib__matplotlib-23476",
    "pydata__xarray-7393",
    "scikit-learn__scikit-learn-14806",
    "pydata__xarray-3364",
    "sphinx-doc__sphinx-11311",
    "django__django-5470",
    "matplotlib__matplotlib-26472",
    "scikit-learn__scikit-learn-13472",
    "scikit-learn__scikit-learn-13628",
    "scikit-learn__scikit-learn-14450",
    "matplotlib__matplotlib-23314",
    "pydata__xarray-6394",
    "scikit-learn__scikit-learn-11043",
    "matplotlib__matplotlib-26249",
    "scikit-learn__scikit-learn-12860",
    "scikit-learn__scikit-learn-10581",
    "django__django-12497",
    "matplotlib__matplotlib-24619",
    "matplotlib__matplotlib-25551",
    "matplotlib__matplotlib-26024",
    "scikit-learn__scikit-learn-10428",
    "matplotlib__matplotlib-24334",
    "scikit-learn__scikit-learn-14496",
    "matplotlib__matplotlib-22815",
    "scikit-learn__scikit-learn-10198",
    "matplotlib__matplotlib-25746",
    "pydata__xarray-6721",
    "matplotlib__matplotlib-24637",
    "matplotlib__matplotlib-25085",
    "scikit-learn__scikit-learn-13641",
    "scikit-learn__scikit-learn-10483",
    "pydata__xarray-3812",
    "matplotlib__matplotlib-23563",
    "matplotlib__matplotlib-25779",
    "scikit-learn__scikit-learn-13017",
    "pydata__xarray-4939",
    "scikit-learn__scikit-learn-10331",
    "matplotlib__matplotlib-25129",
    "scikit-learn__scikit-learn-12989",
    "matplotlib__matplotlib-25404",
    "matplotlib__matplotlib-26089",
    "pydata__xarray-6999",
    "pydata__xarray-3520",
    "scikit-learn__scikit-learn-13363",
    "matplotlib__matplotlib-22835",
    "django__django-8326",
    "django__django-8961",
    "pydata__xarray-5126",
    "matplotlib__matplotlib-24224",
    "scikit-learn__scikit-learn-15096",
    "matplotlib__matplotlib-25027",
    "matplotlib__matplotlib-24768",
    "scikit-learn__scikit-learn-11264",
    "scikit-learn__scikit-learn-14520",
    "pydata__xarray-7444",
    "django__django-7530",
    "scikit-learn__scikit-learn-12908",
    "scikit-learn__scikit-learn-13726",
    "scikit-learn__scikit-learn-13828",
    "scikit-learn__scikit-learn-13704",
    "pydata__xarray-4879",
    "scikit-learn__scikit-learn-11235",
    "scikit-learn__scikit-learn-10803",
    "scikit-learn__scikit-learn-13960",
    "scikit-learn__scikit-learn-14125",
    "scikit-learn__scikit-learn-12760",
    "matplotlib__matplotlib-24691",
    "matplotlib__matplotlib-25479",
    "matplotlib__matplotlib-23348",
    "pydata__xarray-4248",
    "pydata__xarray-6744",
    "pydata__xarray-4419",
    "scikit-learn__scikit-learn-13302",
    "matplotlib__matplotlib-26113",
    "django__django-15689",
    "matplotlib__matplotlib-25651",
    "pydata__xarray-4767",
    "scikit-learn__scikit-learn-11574",
    "matplotlib__matplotlib-26160",
    "scikit-learn__scikit-learn-13439",
    "scikit-learn__scikit-learn-10687",
    "scikit-learn__scikit-learn-12421",
    "scikit-learn__scikit-learn-10452",
    "pydata__xarray-6598",
    "matplotlib__matplotlib-26466",
    "matplotlib__matplotlib-23174",
    "matplotlib__matplotlib-25287",
    "matplotlib__matplotlib-25332",
    "pydata__xarray-4423",
    "scikit-learn__scikit-learn-14024",
    "scikit-learn__scikit-learn-13143",
    "matplotlib__matplotlib-26291",
    "pydata__xarray-4493",
    "pydata__xarray-3302",
    "matplotlib__matplotlib-22883",
    "matplotlib__matplotlib-23031",
    "matplotlib__matplotlib-25079",
    "matplotlib__matplotlib-25425",
    "scikit-learn__scikit-learn-15084",
    "sympy__sympy-19201",
    "scikit-learn__scikit-learn-13333",
    "matplotlib__matplotlib-24013",
    "matplotlib__matplotlib-23057",
    "matplotlib__matplotlib-23964",
    "scikit-learn__scikit-learn-15625",
    "scikit-learn__scikit-learn-8554",
    "scikit-learn__scikit-learn-13174",
    "scikit-learn__scikit-learn-10982",
    "pydata__xarray-4094",
    "matplotlib__matplotlib-25405",
    "pydata__xarray-5187",
    "matplotlib__matplotlib-24362",
    "pydata__xarray-3637",
    "scikit-learn__scikit-learn-13436",
    "scikit-learn__scikit-learn-13392",
    "scikit-learn__scikit-learn-15138",
    "matplotlib__matplotlib-24149",
    "matplotlib__matplotlib-24250",
    "django__django-9003",
    "matplotlib__matplotlib-24257",
    "sympy__sympy-14248",
    "matplotlib__matplotlib-23573",
    "pytest-dev__pytest-10482",
    "scikit-learn__scikit-learn-11578",
    "scikit-learn__scikit-learn-11542",
    "pydata__xarray-5731",
    "scikit-learn__scikit-learn-12258",
    "scikit-learn__scikit-learn-13915",
    "pydata__xarray-5365",
    "scikit-learn__scikit-learn-14141",
    "scikit-learn__scikit-learn-14983",
    "pydata__xarray-7120",
    "pydata__xarray-3733",
    "scikit-learn__scikit-learn-10382",
    "scikit-learn__scikit-learn-10774",
    "scikit-learn__scikit-learn-10844",
    "matplotlib__matplotlib-23188",
    "scikit-learn__scikit-learn-12834",
    "pydata__xarray-4759",
    "scikit-learn__scikit-learn-11333",
    "pydata__xarray-3095",
    "scikit-learn__scikit-learn-10306",
    "scikit-learn__scikit-learn-10397",
    "pydata__xarray-4075",
    "scikit-learn__scikit-learn-11315",
    "django__django-7475",
    "scikit-learn__scikit-learn-9304",
    "scikit-learn__scikit-learn-14704",
    "scikit-learn__scikit-learn-13142",
    "scikit-learn__scikit-learn-10377",
    "matplotlib__matplotlib-22931",
    "scikit-learn__scikit-learn-9274",
    "matplotlib__matplotlib-24403",
    "matplotlib__matplotlib-14043",
    "scikit-learn__scikit-learn-9775",
    "pydata__xarray-4098",
    "sympy__sympy-15222",
    "scikit-learn__scikit-learn-13447",
    "scikit-learn__scikit-learn-15535",
    "scikit-learn__scikit-learn-11391",
    "scikit-learn__scikit-learn-12682",
    "pydata__xarray-6823",
    "matplotlib__matplotlib-26122",
}

import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='swebench',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    python_requires='>=3.8',
    install_requires=[
        'datasets',
        'docker',
        'pre-commit',
        'requests',
        'tqdm',
        'ghapi',
        'GitPython',
        'python-dotenv',
        'requests',
        'bs4',
    ],
    include_package_data=True,
)

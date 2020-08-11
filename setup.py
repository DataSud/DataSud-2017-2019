from setuptools import setup, find_packages


def get_requirements():
    with open('requirements.txt') as req_file:
        reqs = req_file.readlines()
    return [req for req in reqs if not req.startswith('-e')]


def get_long_description():
    with open('README.md', 'rb') as desc_file:
        description = desc_file.read().decode('utf-8')
    return description


setup(
    name="idgo",
    descrtiption="Site d'administration d'IDGO",
    packages=find_packages(),
    long_description=get_long_description(),
    url='https://github.com/neogeo-technologies/idgo',
    install_requires=get_requirements()
)


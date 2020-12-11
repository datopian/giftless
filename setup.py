from setuptools import find_packages, setup

setup(
    name='giftless',
    packages=find_packages(exclude='./tests'),
    version=open('VERSION').read(),
    description='A Git LFS Server implementation in Python with support for pluggable backends',
    author='Shahar Evron',
    author_email='shahar.evron@datopian.com',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    install_requires=[
        'figcan',
        'flask',
        'flask-marshmallow',
        'marshmallow-enum',
        'pyyaml',
        'PyJWT',
        'webargs',
        'python-dotenv',
        'typing-extensions',
        # This is currently unsupported by pypi: pull unreleased version of Flask-classful directly from GitHub
        # 'flask-classful @ https://codeload.github.com/teracyhq/flask-classful/tar.gz/3bbab31705b4aa2903e7e62aa8c5ee70a1e6d789#egg=flask-classful-0.15.0',
        'flask-classful',
    ],
    package_data={}
)

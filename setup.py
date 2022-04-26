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
        'flask-classful',
    ],
    include_package_data=True
)

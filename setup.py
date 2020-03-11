from setuptools import setup

setup(
    name='giftless',
    packages=['giftless'],
    version=open('VERSION').read(),
    description='A Git LFS Server implementation in Python with support for pluggable backends',
    author='Shahar Evron',
    author_email='shahar.evron@datopian.com',
    install_requires=[
        'figcan',
        'flask',
        'flask-classful',
        'flask-marshmallow',
        'marshmallow-enum',
        'pyyaml',
        'PyJWT',
        'webargs'
    ],
    package_data={}
)

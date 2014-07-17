from setuptools import setup, find_packages

setup(
    name='tx-easy-pika',
    version='1.0',
    author='SweetIQ',
    author_email='rob@sweetiq.com',
    description=('Wrapper around Pika\'s Twisted connection to make it simpler to work with.'),
    packages=find_packages(),
    install_requires=[
        'Twisted==14.0.0'
    ],
    url='http://github.com/SweetIQ/tx-easy-pika',
    keywords=["pika", "rabbitmq", "twisted", "amqpy"],
    package_data={"tx-easy-pika": ["requirements.txt"]},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: MIT License",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers"
    ],
    long_description="""\
  Easy Pika - Twisted
  ---------------------------------

  A wrapper around Pika's Twisted components to make it easier to work with.
""",
)

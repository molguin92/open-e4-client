import setuptools

setuptools.setup(
    name="e4client",
    version="0.0.1",
    author="Manuel Olguin Munoz",
    author_email="molguin@kth.se",
    description="Simple, pure Python 3.7 client for the "
                "Empatica E4 streaming server.",
    long_description_content_type="text/markdown",
    url="https://github.com/molguin92/open-e4-client",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires='>=3.7',
    install_requires=[]
)

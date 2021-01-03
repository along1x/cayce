import setuptools as st

requirements = [
    "beautifulsoup4 >= 4.8.2",
    "pandas >= 1.0.5",
    "wget >= 3.2",
]

st.setup(
    name="cayce",
    version="0.1.2",
    author="Andrew Long",
    author_email="andrewmlong@hotmail.com",
    description="Tools to search and download filing data from SEC EDGAR",
    url="https://github.com/along1x/cayce",
    packages=st.find_packages(),
    install_requires=requirements,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero GPL",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)

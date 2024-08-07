from setuptools import setup, find_packages

setup(
    name="VpngateClientWin",  # 项目名称
    version="1.0.0",  # 版本号
    author="Sinspired",  # 作者
    author_email="ggmomo@gmail.com",  # 作者邮箱
    description="A VPN client for connecting to VPNGate servers.",  # 简短描述
    long_description=open("README.md").read(),  # 读取README文件作为长描述
    long_description_content_type="text/markdown",  # 长描述的内容格式
    keywords="vpn openvpn client",
    url="https://github.com/sinspired/VpngateClientPyWin",  # 项目主页
    # packages=find_packages(),  # 自动发现并打包所有模块
    packages=find_packages(include=["VpngateClient", "VpngateClient.*"]),
    include_package_data=True,  # 包含包内的数据文件
    classifiers=[
        "Programming Language :: Python :: 3",  # 支持的Python版本
        "License :: OSI Approved :: MIT License",  # 许可证
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.3",  # 支持的Python版本
    install_requires=[  # 项目的依赖包
        "requests",
        "console",
    ],
    entry_points={
        "console_scripts": [
            "VpngateClientPyWin=VpngateClient.VpngateClient:main",
            "VpngateClientWin=VpngateClient.VpngateClient:main",
            "vpngateclient=VpngateClient.VpngateClient:main",
            "vpngate=VpngateClient.VpngateClient:main",
        ],
    },
)

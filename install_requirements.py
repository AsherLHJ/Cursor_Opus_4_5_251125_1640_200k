import subprocess
import sys
import os

def install_requirements():
    """一键安装本项目所需的 Python 依赖"""
    print("=== 开始安装 AutoPaperWeb 所需的依赖库 ===\n")

    # 需要安装的库列表
    required_packages = [
        'openai',                 # OpenAI 兼容 SDK（用于调用火山引擎 Ark 接口）
        'mysql-connector-python', # 从数据库读取 API 密钥、论文信息
        'bcrypt',                 # 安全密码哈希
        'redis'                   # Stage3：Redis 用于限流与队列
    ]
    print("正在升级pip...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
        print("✓ pip升级成功\n")
    except Exception as e:
        print(f"✗ pip升级失败: {e}\n")
    
    # 安装每个包
    for package in required_packages:
        print(f"正在安装 {package}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ {package} 安装成功\n")
        except Exception as e:
            print(f"✗ {package} 安装失败: {e}\n")
    
    print("=== 依赖库安装完成 ===\n")

    # 目录初始化说明：当前流程不强制依赖本地 Data/Result/Log 目录，
    # 如需使用本地目录（例如本地开发者模式自定义路径），程序会在运行时自动创建。

    print("\n=== 安装完成！===")
    print("\n下一步：")
    print("1. 在数据库 PaperDB 的表 api_list 中添加至少一条可用的 API Key（列：api_key，up=1）")
    print("2. 在 config.json 中确认/修改数据库连接、语言等配置（本地开发者模式见 docs/LocalDevelop.md）")
    print("3. 运行 python main.py 启动本地服务并访问 http://127.0.0.1:8080/")

if __name__ == "__main__":
    install_requirements()
    input("\n按回车键退出...")

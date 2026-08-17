from http.client import responses
import requests
import logging
import time
import json
import random
from datetime import datetime
import socket

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# ===== 配置区域 =====
# Push Plus推送配置
PUSH_PLUS_TOKEN = ""  # 你的Push Plus Token

# 微信步数账号配置 - 可以添加多个账号
ACCOUNTS = [

    {
        "username": "2805943187@qq.com",  # 手机号
        "password": "aa123456789.",  # 密码
    }
]

# 步数配置
MIN_STEPS = 44444  # 最小步数
MAX_STEPS = 66666  # 最大步数
SPECIFIED_STEPS = None  # 指定步数(如果为None则使用随机步数)


# ===== 配置结束 =====

def push_plus_push(token, title, content):
    """Push Plus推送函数"""
    if not token:
        logging.info("未配置Push Plus Token，跳过推送")
        return False

    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "txt"
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                logging.info("Push Plus推送成功")
                return True
            else:
                logging.error(f"Push Plus推送失败: {result.get('msg')}")
                return False
        else:
            logging.error(f"Push Plus推送失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Push Plus推送异常: {e}")
        return False


def test_domain_resolution(domain):
    """测试域名解析"""
    try:
        ip = socket.gethostbyname(domain)
        logging.info(f"域名解析成功: {domain} -> {ip}")
        return True, ip
    except Exception as e:
        logging.error(f"域名解析失败: {domain} - {str(e)}")
        return False, None


def submit_wechat_steps(username, password, steps=None):
    """提交微信步数函数 - 支持多个备用接口"""
    if steps is None:
        steps = random.randint(MIN_STEPS, MAX_STEPS)

    # 多个备用接口配置
    api_configs = [
        {
            "name": "主接口",
            "url": f"http://stjxyp.dpdns.org/index.php?user={username}&pwd={password}&step={steps}&token=8879725",
            "method": "get"
        },
        {
            "name": "备用接口1",
            "url": f"http://api.zhuolin.wang/api/step?user={username}&pwd={password}&step={steps}",
            "method": "get"
        },
        {
            "name": "备用接口2",
            "url": f"http://www.yundongfuwu.com/api/step?user={username}&pwd={password}&step={steps}",
            "method": "get"
        },
        {
            "name": "备用接口3（POST方式）",
            "url": "http://api.wechat-step.com/submit",
            "method": "post",
            "data": {
                "username": username,
                "password": password,
                "steps": steps
            }
        }
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/140.0.7339.128 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json'
    }

    # 先测试主接口的域名解析
    logging.info(f"正在检查主接口域名...")
    domain_success, ip = test_domain_resolution('stjxyp.dpdns.org')
    if not domain_success:
        logging.warning("主接口域名解析失败，将尝试备用接口")

    # 尝试所有接口
    for i, config in enumerate(api_configs, 1):
        try:
            logging.info(f"尝试接口 {i}/{len(api_configs)}: {config['name']}")

            if config.get('method', 'get').lower() == 'get':
                response = requests.get(config['url'], headers=headers, timeout=15)
            else:  # POST请求
                response = requests.post(
                    config['url'],
                    json=config.get('data', {}),
                    headers=headers,
                    timeout=15
                )

            logging.info(f"接口 {i} 响应状态码: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    logging.info(f"接口 {i} 响应内容: {result}")

                    # 检查多种可能的成功状态
                    if (result.get('status') == "success" or
                            result.get('code') == 200 or
                            result.get('success') == True or
                            result.get('msg') == "成功"):
                        return True, f"微信步数提交成功! 步数: {steps} (使用{config['name']})", steps
                    else:
                        error_msg = result.get('data', result.get('msg', result.get('message', '未知错误')))
                        logging.warning(f"接口 {i} 返回失败: {error_msg}")
                        continue
                except json.JSONDecodeError:
                    # 如果不是JSON响应，检查文本内容
                    if "成功" in response.text or "success" in response.text.lower():
                        return True, f"微信步数提交成功! 步数: {steps} (使用{config['name']})", steps
                    else:
                        logging.warning(f"接口 {i} 返回非JSON格式: {response.text[:100]}")
                        continue
            else:
                logging.warning(f"接口 {i} 状态码异常: {response.status_code}")
                continue

        except requests.exceptions.Timeout:
            logging.warning(f"接口 {i} 请求超时")
            continue
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"接口 {i} 连接错误: {str(e)[:100]}")
            continue
        except Exception as e:
            logging.warning(f"接口 {i} 请求异常: {str(e)[:100]}")
            continue

    # 所有接口都失败了
    error_msg = f"所有接口均失败，请检查网络或更新接口地址 (目标步数: {steps})"
    logging.error(error_msg)
    return False, error_msg, steps


def daily_task():
    """
    每日任务流程：提交微信步数并发送通知
    """
    logging.info("开始执行每日任务")

    # 检查账户配置
    if not ACCOUNTS:
        logging.error("未配置账户信息，请在脚本中修改ACCOUNTS列表")
        return False

    # 工作日问候语
    weekday_dict = {
        0: "周一",
        1: "周二",
        2: "周三",
        3: "周四",
        4: "周五",
        5: "周六",
        6: "周日"
    }
    weekday = datetime.now().weekday()
    greeting = f"{weekday_dict.get(weekday, '工作日')}愉快！"

    # 处理所有账户
    results = []
    success_count = 0

    for i, account in enumerate(ACCOUNTS, 1):
        username = account["username"]
        password = account["password"]

        logging.info(f"正在处理第 {i} 个账户: {username}")

        # 提交微信步数
        success, step_message, step_count = submit_wechat_steps(
            username,
            password,
            SPECIFIED_STEPS
        )

        result = {
            "username": username,
            "success": success,
            "message": step_message,
            "steps": step_count
        }
        results.append(result)

        if success:
            success_count += 1

        logging.info(f"账户 {username} 处理结果: {step_message}")

        # 多个账户之间添加延迟
        if i < len(ACCOUNTS):
            delay = random.randint(5, 15)
            logging.info(f"等待 {delay} 秒后处理下一个账户...")
            time.sleep(delay)

    # 构造推送内容
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"微信步数提交报告 - {current_time}"

    # 根据星期决定表情符号
    emoji = "&#128522;" if weekday < 5 else "&#128526;"

    content = f"{greeting}{emoji}\n"
    content += f"执行时间: {current_time}\n"
    content += f"处理账户数: {len(ACCOUNTS)}\n"
    content += f"成功数量: {success_count}\n"
    content += f"失败数量: {len(ACCOUNTS) - success_count}\n"
    content += "=" * 30 + "\n"

    for result in results:
        status_icon = "&#9989;" if result["success"] else "&#10060;"
        content += f"{status_icon} {result['username']}: {result['message']}\n"

    # 发送Push Plus推送
    if PUSH_PLUS_TOKEN:
        logging.info("正在发送Push Plus推送通知...")
        push_result = push_plus_push(PUSH_PLUS_TOKEN, title, content)
        if push_result:
            logging.info("推送发送成功")
        else:
            logging.error("推送发送失败")
    else:
        logging.info("未配置PUSH_PLUS_TOKEN，跳过推送")
        # 如果没有配置推送，则在控制台输出结果
        print("\n" + "=" * 50)
        print(content)

    logging.info(f"每日任务完成! 成功: {success_count}/{len(ACCOUNTS)}")
    return success_count > 0


def handler(*args):
    daily_task()


if __name__ == "__main__":
    # 直接执行任务
    daily_task()
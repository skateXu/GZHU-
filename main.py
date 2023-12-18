import os
import time
from datetime import datetime,timedelta
import configparser
import json
import requests
import re
import execjs
from lxml import etree


class Config(object):
    def __init__(self):
        self.config_ini = configparser.ConfigParser()
        self.file_path = os.path.join(os.path.abspath('.'), 'config.ini')
        self.config_ini.read(self.file_path, encoding='utf-8')
        base_info = dict(self.config_ini.items('baseinfo'))
        self.username = base_info['username']
        self.password = base_info['password']

    def set_config(self):
        un = input('输入登录学号 > ')
        pw = input('输入登录密码 > ')
        self.config_ini.set('baseinfo', 'username', un)
        self.config_ini.set('baseinfo', 'password', pw)
        self.config_ini.write(open(self.file_path, 'w', encoding='utf-8'))


def rsa(username, password, lt):
    js_res = requests.get('https://newcas.gzhu.edu.cn/cas/comm/js/des.js')
    context = execjs.compile(js_res.text)
    result = context.call("strEnc", username + password + lt, '1', '2', '3')
    return result


class GZHU(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.client = requests.session()

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Host': 'yqtb.gzhu.edu.cn',
            'Origin': 'http://yqtb.gzhu.edu.cn',
            'Referer': 'https://yqtb.gzhu.edu.cn/infoplus/form/XNYQSB/start',
        }
        
        self.datas = {
            'csrfToken': '',
        }


    def login(self):
        login_url = 'https://newcas.gzhu.edu.cn/cas/login'
        res = self.client.get(url=login_url)
        # print(res.text)
        
        lt = re.findall(r'id="lt" name="lt" value="(.*)"', res.text)[0]
        execution = re.findall(r'name="execution" value="(.*)"', res.text)[0]
        login_form = {
            'rsa': rsa(self.username, self.password, lt),
            'ul': len(self.username),
            'pl': len(self.password),
            'lt': lt,
            'execution': execution,
            '_eventId': 'submit',
        }
        res = self.client.post(url=login_url, data=login_form)
        # print(res.text)

        selector = etree.HTML(res.text)
        if selector.xpath('//title/text()')[0] == '融合门户':  # 融合门户主页面
            return True
        else:
            return False


    def start_report(self):
        self.client.get('https://yqtb.gzhu.edu.cn/infoplus/form/XNYQSB/start')

        start_report_url = 'https://yqtb.gzhu.edu.cn/infoplus/interface/start'
        start_report_Data = {'idc': 'XNYQSB',}
        res = self.client.post(url=start_report_url, data=start_report_Data, headers=self.headers)
        # print(res.text)

        if '"ecode":"SAFETY_PROTECTION_CSRF"' in res.text:
            self.datas['csrfToken'] = re.findall(r'"entities":\["(.*)"\]', res.text)[0]  # 获取 csrfToken
            start_report_Data.update(self.datas) # 加上csrfToken
            res = self.client.post(url=start_report_url, data=start_report_Data, headers=self.headers)
            # print(res.text)

            if '"ecode":"SUCCEED"' in res.text:
                self.headers['Referer'] = re.findall(r'"entities":\["(.*)"\]', res.text)[0]  # 修改 Referer
                print('成功获取打卡url: ' + self.headers['Referer'])
                return True
            else:
                print('无法获取打卡url')
                return False
        else:
            print('无法获取csrfToken')
            return False


    def submit(self):
        getdata_url = 'https://yqtb.gzhu.edu.cn/infoplus/interface/render'
        url_id = re.findall(r'form\/(.*)\/render', self.headers['Referer'])[0] # 获取url_id
        getdata_data = {
            'stepId': int(url_id),
            'csrfToken': self.datas['csrfToken'],
        }
        res = self.client.post(url=getdata_url, data=getdata_data, headers=self.headers)
        # print(res.text)

        if '"ecode":"SUCCEED"' in res.text:
            today = datetime.now()
            print('当前日期：' + str(today.strftime("%Y-%m-%d")))
            x = int(input('输入核酸距离天数：'))
            checkday = datetime.now() - timedelta(days = x)
            print('核酸日期：' + str(checkday.strftime("%Y-%m-%d")))
            
            auto_data = json.loads(re.findall(r'"data":(.*),"snapshots"', res.text)[0])  # 获取自动填写的 data
            extra_data = {
                'fieldZJYCHSJCYXJGRQzd': int(time.mktime(checkday.timetuple())),  # 最近一次核酸结果日期
                'fieldSTQKbrstzk1': '1',  # 本人身体状况
                'fieldJKMsfwlm': '1',  # 健康码是否为绿码
                'fieldCXXXsftjhb': '2',  # 7 天内是否前往疫情重点地区
                'fieldCNS': True,  # 本人承诺对上述填报内容真实性负责，如有不实，本人愿意承担一切责任
            }
            Json = auto_data
            Json.update(extra_data)

            submit_url_1 = 'https://yqtb.gzhu.edu.cn/infoplus/interface/listNextStepsUsers'
            submit_data = {
                'stepId': int(url_id),
                'actionId': 1,
                'csrfToken': self.datas['csrfToken'],
                'lang': 'zh',
                'timestamp': Json['_VAR_NOW'],
                'formData': json.dumps(Json).encode('utf-8'),
            }
            res = self.client.post(url=submit_url_1, data=submit_data, headers=self.headers)
            # print(res.text)

            if '"ecode":"SUCCEED"' in res.text:
                submit_url_2 = 'https://yqtb.gzhu.edu.cn/infoplus/interface/doAction'
                submit_data.update({'nextUsers':'{}'})
                res = self.client.post(url=submit_url_2, data=submit_data, headers=self.headers)
                # print(res.text)

                if '"error":"打卡成功"' in res.text:
                    return True
                else:
                    print('step_2失败')
                    return False
            else:
                print('step_1失败')
                return False
        else:
            print("无法获取data")
            return False


if __name__ == '__main__':
    menu = """
GZHU健康打卡 更新日期:2022-11-11

0 : 修改配置信息
1 : 健康打卡
2 : 退出
"""
    while True:
        os.system('cls')
        print(menu)
        choice = input('输入操作前面的数字标号，按回车确定 > ')
        print()
        try:
            config = Config()
        except:
            print('配置文件不正确\n')
            os.system('pause')
            break

        if choice == '0':
            config.set_config()
            print()
            os.system('pause')

        elif choice == '1':
            g = GZHU(config.username, config.password)
            print('当前账号：' + config.username)
        
            print('\n正在登录教务系统...')
            if g.login():
                print('登录成功！')
                if g.start_report():
                    print('\n开始上报...')
                    if g.submit():
                        print('\n打卡成功！')
                    else:
                        print('\n打卡失败！')
                else:
                    print('\n开始上报失败！')
            else:
                print('登录失败！')
            
            print()
            os.system('pause')

        elif choice == '2':
            os.system('pause')
            os._exit(0)


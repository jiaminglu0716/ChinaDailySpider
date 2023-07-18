import requests
from lxml import etree
from os.path import exists
from time import sleep
import json
import re


# 粗略写的存储类
class Item(object):
    data = []

    def __init__(self):
        pass

    def add(self, val):
        self.data.append(val)

    def empty(self):
        return len(self.data) == 0

    def load(self, file_path):
        # 查看是否存在该文件
        res = exists(file_path)
        if res:
            # 存在则进行数据导入
            with open(file_path, 'r') as fp:
                # json.loads 用于将 json 数据转换为 python 可识别的 dict 字典格式
                # 这里的文件只有一行所以直接用索引 0 取出相应的 json 字符
                self.data = json.loads(fp.readlines()[0])
                # 关闭文件流
                fp.close()
        # 返回文件加载状态
        # 这里没有进行具体的排错机制,所以尽可能按格式导入
        return res

    def json_save(self, filename):
        # 与上面相反,这里是将 python 格式的文件转 json 格式
        j_data = json.dumps(self.data)
        with open(filename, 'w', newline='') as fp:
            fp.writelines(j_data)
            fp.close()

    # 遍历列表数据
    def show(self):
        for val in self.data:
            print(val)


# 核心的ChinaDaily爬虫
class ChinaDaily(object):
    url = "https://www.chinadaily.com.cn/"
    # 初始化两个存储类,用于数据添加和保存
    list_item = Item()  # 导航栏数据
    passages_item = Item()  # 二级列表文章的简略信息

    def __init__(self):
        # 初始化文件存储位置,这里懒得添加参数,就默认当前目录的该文件
        self.list_file = 'ChinaDailyListInfo.json'
        self.cont_file = 'ChinaDailyNews.json'
        pass

    # @staticmethod 静态方法, 意味着该方法无法直接调用该对象的属性, 不声明则可以外置该函数
    @staticmethod
    def purl(url):
        # 主要用于纠正所爬取到的url的格式(比如少了http则帮其添加, 不属于该类型的则可以排除)
        return f'http:{url}' if url.startswith('//') else url

    @staticmethod
    def get(url):
        # verify 主要是为了方便完成而设置
        return requests.get(url=url, verify=False).text

    # 获取导航专栏的页面信息
    def get_nav_info(self):
        # etree 主要用于网页元素标签的识别
        # etree.HTML(网页内容) 则会返回元素搜索器,必须由内部方法获取内容
        # 这里则使用浏览器都可使用的 xpath, 浏览器变为 $x 即可
        # xpath 中 //:完全匹配, /:局部匹配 后面紧随的则是标签名字比如 <div></div> 那么xpath则是 xpath('//div')
        # 标签的属性则用 [@属性名=属性值],比如<a class='bb'>ll</a>匹配对象可以是 xpath('//a[@class="bb"]')
        # 获取属性值则是 a/@class , 获取文本内容 ll 则是 a/text()
        # 只要前面没有 / or // 且 后面仍由子元素,则可以继续在新的变量名用 xpath
        # 一般来说 xpath 是以数组的形式返回
        e = etree.HTML(self.get(self.url))
        # 爬取一级目录
        lis = e.xpath('//div[@class="topNav"]//li')
        for li in lis:
            url = li.xpath('a/@href')[0]
            # 排除非法的 url 信息项
            # startswith() 以什么开头,一般为字符串的方法
            if url.startswith('//') or url.startswith('http'):
                # 用于临时记录二级目录的信息
                temp = []

                url = self.purl(url)
                e2 = etree.HTML(self.get(url))
                # 二级目录爬取
                lis2 = e2.xpath('//div[@class="topNav2_art"]//li')
                for li2 in lis2:
                    temp.append({"url": self.purl(li2.xpath('a/@href')[0]),
                                 "title": li2.xpath('a/text()')[0]})
                # 将目录信息添加到存储类中
                self.list_item.add({"url": url,
                                    "title": li.xpath('a/text()')[0],
                                    "list": temp})
        # 保存数据以 json 的形式
        self.list_item.json_save(self.list_file)

    # 获取导航栏信息
    def nav_info(self):
        # 检测是否为空
        if self.list_item.empty():
            # 加载数据是否不成功
            if not self.list_item.load(self.list_file):
                # 重新获取信息
                self.get_nav_info()
        # 由于上面是数据信息的加载判断,此刻可以被断定存在数据.
        return self.list_item.data

    # 获取二级目录表的最大页数
    def list_2_max_page(self, url):
        e = etree.HTML(self.get(url))
        btns = e.xpath('//div[@id="div_currpage"]//a')
        # 这里是通过切换按钮的最后一个直接获取, 不排除最后一页会改变(自行判断)
        l_url = btns[len(btns) - 1].xpath('@href')[0]
        # 由于这里是url信息,那么这里则使用到正则进行数字的匹配
        # rfind是从右到左以该符号为开头的字串
        # re.findall(正则表达式, 匹配字串) 这里作用看英文
        # [0-9]指的是该字符的范围是0-9, 后面的*为字符的匹配个数在0-infinity的范围中
        # 由于 findall 以数组的方式返回, 且有多余冗杂的元素, 为了方便则进行无字串拼接 ''.join(字串数组)
        # 再用 int 进行元素类型的转换,转换为数字型
        max_page = int(''.join(re.findall(r'[0-9]*', l_url[l_url.rfind('/'):])))
        return max_page

    # 这个简单来说就是循环页面进行爬取,利用下面的方法
    def list_2_info(self, url, sta_page, end_page, time=1):
        for i in range(sta_page, end_page + 1):
            self.list_2_page_info(url, i)
            # 睡一下,以免被反爬虫
            sleep(time)

    # 二级目录列表解析
    def list_2_page_info(self, url, page):
        e = etree.HTML(self.get(f"{url}/page_{str(page)}.html"))
        # 寻找列表中的普遍格式的元素项
        # 出于时间,这就写出现最多的项
        items = e.xpath('//div[@class="lft_art"]//div[@class="mb10 tw3_01_2 "]')
        # 获取各项信息,并添加的存储类
        for val in items:
            self.passages_item.add({"title": val.xpath('span/h4/a/text()')[0],
                                    "url": self.purl(val.xpath('span/h4/a/@href')[0]),
                                    "date": val.xpath('span/b/text()')[0]})

    def detail_info(self, url):
        e = etree.HTML(self.get(url))

        # 这个ChinaDaily有点麻烦main_art中的标签时而并不一致,所以实在不行用main_art顶着
        # xpath 当无法匹配到元素时则会返回空数组,数量为 0 ,len可以判断数组的长度
        # python 的行内 if 语法为: 满足时 if 条件 else 不满足时
        aml = e.xpath('//div[@id="lft-art"]')
        article = aml[0] if len(aml) != 0 else e.xpath('//div[@class="main_art"]')[0]

        # ---- 文章信息栏目 ---- #
        info = article.xpath('//div[@class="info"]')[0]
        # 作家 | 地点 | 日报 | 更新时间
        l_info = info.xpath('span[@class="info_l"]/text()')[0]
        # 社交平台（该处忽略不爬取）：Fackbook | Twitter | Linkedin | More
        # r_info = info.xpath('span[@class="info_r"]')

        # ---- 文章内容详情 ---- #
        content = article.xpath('//div[@id="Content"]')[0]
        # 图片信息
        # figure = content.xpath('figure')[0]
        # if len(figure) != 0:
        #     img_info = {"url": figure.xpath('img/@src')[0], "figure": figure.xpath('figcaption/text()')}
        # 文章段落内容
        cont = ''   # 使用该变量将文章内容合在一起
        for p in content.xpath('p'):
            t = p.xpath('strong')
            # 判断文章是否有黑色加粗的标题，并在两边加 -- 来表示
            if len(t) != 0:
                cont += f"// {t[0].xpath('text()')[0]} //\n\n"
            else:
                pc = p.xpath('text()')
                cont += f"{'' if len(pc) == 0 else pc[0]}\n\n"

        return {"title": article.xpath('//h1/text()')[0],
                "info": l_info,  # 如需信息细分，请自行使用字符切片进行处理
                "content": cont}

    def save(self):
        # 保存
        self.passages_item.json_save(self.cont_file)


if __name__ == '__main__':
    # 类对象声明
    cd = ChinaDaily()
    # 或取 一级目录 world 的 二级目录 亚洲 目录的 1 到 2 页
    cd.list_2_info("http://www.chinadaily.com.cn/world/asia_pacific", 1, 2)
    # 保存目录列表
    cd.save()
    # 加载目录文件
    cd.passages_item.load(cd.cont_file)
    # 获取目录文章的详细文章内容
    with open("ChinaDailyC.txt", 'w', newline='', encoding='utf-8') as f:
        for item in cd.passages_item.data:
            # 这里的 get 是通过字典的 key 获取 val. 比如: g = {"m": "fa"}, g.get("m") 则可以得到 "fa"
            print(item.get('url'))
            # 获取详情页信息
            detail = cd.detail_info(item.get('url'))
            f.write('\n==========\n')
            f.write(detail.get('title'))
            f.write('\n==========\n')
            f.write(detail.get('content'))
        # 关闭文件流
        f.close()

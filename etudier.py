#!/usr/bin/env python3

import sys
import requests_html

web = requests_html.HTMLSession()

url = sys.argv[1]

r = web.get(url)

r.html.render()

for e in r.html.find('.gs_r'):
    print(e.find('.gs_rt a', first=True).text)


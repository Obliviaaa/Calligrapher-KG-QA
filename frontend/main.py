# -*- coding: utf-8 -*-
from web_app import app
import uvicorn

if __name__ == '__main__':
    print('\n' + '='*60)
    print('中国书法家知识图谱问答系统')
    print('='*60)
    print('\n系统功能：')
    print('  🏠 首页 - 自然语言问答界面')
    print('  🔍 SPARQL查询 - 专业SPARQL查询界面')
    print('  🕸️ 关系网络 - 交互式人物关系可视化')
    print('  🏛️ 流派分析 - 书法流派分析')
    print('\n启动服务...')
    print('前端地址: http://localhost:8001')
    print('SPARQL Endpoint: http://localhost:8000')
    print('='*60 + '\n')
    uvicorn.run(app, host='0.0.0.0', port=8001)

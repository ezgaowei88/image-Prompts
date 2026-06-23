工作流程
启动服务器：运行 python server.py，然后访问 http://localhost:8000
新增案例：上传图片时，前端通过 POST /api/upload 将图片保存到 images/{category}/{category}_case_local_{timestamp}/output.jpg
编辑案例：替换图片时同样通过 API 保存到对应文件夹
删除案例：通过 POST /api/delete 删除对应的图片文件夹
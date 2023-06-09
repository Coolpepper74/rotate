import fastapi.responses
import numpy
import io
import requests
from PIL import Image, ImageDraw
from matplotlib import pyplot as plt
from fastapi import FastAPI, Request, UploadFile, Form, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List
import hashlib
import uvicorn
import numpy as np
from pydantic import BaseModel
from googleapiclient.errors import HttpError

app = FastAPI()
# Hello World route
def sum_two_args(x,y):
    return x+y
# Hello World route
@app.get("/")
def read_root():
    return {"Hello": "World"}

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
@app.get("/some_url/{something}", response_class=HTMLResponse)
async def read_something(request: Request, something: str):
 return templates.TemplateResponse("some.html", {"request": request,
"something": something})

def create_some_image(some_difs):
    imx = 200
    imy = 200
    image = numpy.zeros((imx,imy, 3), dtype=numpy.int8)
    image[0:imy//2,0:imx//2,0] = some_difs
    image[imy//2:,imx//2:,2] = 240
    image[imy//2:,0:imx//2, 1] = 240
    return image
# возврат изображения в виде потока медиаданных по URL
@app.get("/bimage", response_class=fastapi.responses.StreamingResponse)
async def b_image(request: Request):
    # рисуем изображение, сюда можете вставить GAN, WGAN сети и т. д.
    # взять изображение из массива в Image PIL
    image = create_some_image(100)
    im = Image.fromarray(image, mode="RGB")
    # сохраняем изображение в буфере оперативной памяти
    imgio = io.BytesIO()
    im.save(imgio, 'JPEG')
    imgio.seek(0)
    # Возвращаем изображение в виде mime типа image/jpeg
    return fastapi.responses.StreamingResponse(content=imgio, media_type="image/jpeg")
# возврат двух изображений в таблице html, одна ячейка ссылается на url bimage
# другая ячейка указывает на файл из папки static по ссылке
# при этом файл туда предварительно сохраняется после генерации из массива
@app.get("/image", response_class=HTMLResponse)
async def make_image(request: Request):
    image_n = "image.jpg"
    image_dyn = request.base_url.path+"bimage"
    image_st = request.url_for("static", path = f'/{image_n}')
    image = create_some_image(250)
    im = Image.fromarray(image, mode="RGB")
    im.save(f"./static/{image_n}")
    # передаем в шаблон две переменные, к которым сохранили url
    return templates.TemplateResponse("image.html", {"request": request,"im_st":image_st, "im_dyn": image_dyn})

@app.post("/image_form", response_class=HTMLResponse)
async def make_image(request: Request,
    name_op:str = Form(),
    number_op:int = Form(),
    r:int = Form(),
    g:int = Form(),
    b:int = Form(),
    files: List[UploadFile] = File(description="Multiple files as UploadFile")
 ):
    # устанавливаем готовность прорисовки файлов, можно здесь проверить, что файлы вообще есть
    # лучше использовать исключения
    ready = False
    print(len(files))
    if(len(files)>0):
        if(len(files[0].filename)>0):
            ready = True
    images = []
    if ready:
        print([file.filename.encode('utf-8') for file in files])
        # преобразуем имена файлов в хеш -строку
        images = ["static/"+hashlib.sha256(file.filename.encode('utf-8')).hexdigest() for file in files]
        # берем содержимое файлов
        content = [await file.read() for file in files]
        # создаем объекты Image типа RGB размером 200 на 200
        p_images = [Image.open(io.BytesIO(con)).convert("RGB").resize((200,200)) for con in content]
        # сохраняем изображения в папке static
        for i in range(len(p_images)):
            draw = ImageDraw.Draw(p_images[i])
            # Рисуем красный эллипс с черной окантовкой
            draw.ellipse((100, 100, 150, 200+number_op), fill=(r,g,b), outline=(0, 0, 0))
            p_images[i].save("./"+images[i],'JPEG')
        # возвращаем html с параметрами-ссылками на изображения, которые позже будут
        # извлечены браузером запросами get по указанным ссылкам в img src
    return templates.TemplateResponse("forms.html", {"request": request, "ready": ready, "images": images})

@app.get("/image_form", response_class=HTMLResponse)
async def make_image(request: Request):
    return templates.TemplateResponse("forms.html", {"request": request})

class User(BaseModel):
    name: str
    age: int
@app.get('/users/{user_id}')
def get_user(user_id):
    return User(name="Joe Biden", age=80)
@app.put('/users/{user_id}')
def update_user(user_id, user: User):
# поместите сюда код для обновления данных
    return user

def hist(list, last_name, n):
    r, g, b = list[:, :, 0], list[:, :, 1], list[:, :, 2]
    print(r, g, b)
    plt.hist(r.flatten(), bins=256, color='red', alpha=0.5)
    plt.hist(g.flatten(), bins=256, color='green', alpha=0.5)
    plt.hist(b.flatten(), bins=256, color='blue', alpha=0.5)
    # plt.show()
    plt.savefig(f"static/plot{n}.png")
    img = Image.fromarray(list)
    plt.imshow(img)
    img.save("./" + last_name + ".jpeg", 'JPEG')
    plt.clf()
    return

@app.post("/rotate", response_class=HTMLResponse)
async def rotate_image(request: Request,
    capt: str = Form(),
    a:int = Form(),
    files: List[UploadFile] = File(description='Multiple files as UploadFile')
 ):
    recaptcha_response = capt
    print(recaptcha_response)
    try:
        if not recaptcha_response:
            return HTMLResponse('<h1>reCAPTCHA verification failed</h1>')
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': '6LdD6wEmAAAAAHqrZC_aAjmEIxZTsbQJgm78350J',
                'response': recaptcha_response,
            },
        )
        if not response.json().get('success'):
            return HTMLResponse('<h1>reCAPTCHA verification failed</h1>')
    except HttpError as e:
            raise HTTPException(status_code=500, detail=str(e))
    ready = False
    print(len(files))
    if(len(files)>0):
        if(len(files[0].filename)>0):
            ready = True
    if ready:
        print([file.filename.encode('utf-8') for file in files])
        # преобразуем имена файлов в хеш -строку
        images = ["static/"+hashlib.sha256(file.filename.encode('utf-8')).hexdigest() for file in files]
        # берем содержимое файлов
        last_name = "static/" + hashlib.sha256(
            files[0].filename.encode('utf8')).hexdigest()
        content = [await file.read() for file in files]
        # создаем объекты Image типа RGB размером 200 на 200
        p_images = [Image.open(io.BytesIO(con)).convert("RGB").resize((200,200)) for con in content]
        o_list = []
        p_list = []
        for i in range(len(p_images)):
            o_array = np.array(p_images[i])
            o_list.append(o_array)
        for i in range(len(p_images)):
            p_images[i] = p_images[i].rotate(a)
            p_images[i].save("./"+images[i],'JPEG')
        for i in range(len(p_images)):
            p_array = np.array(p_images[i])
            p_list.append(p_array)
        hist(o_list[0], last_name, 1)
        hist(p_list[0], last_name, 2)
        rets = [f"{last_name}.jpeg", 'static/plot1.png', 'static/plot2.png']


        # возвращаем html с параметрами-ссылками на изображения, которые позже будут
        # извлечены браузером запросами get по указанным ссылкам в img src
    return templates.TemplateResponse("rotate.html", {"request": request, "ready": ready, "images": rets})

@app.get("/rotate", response_class=HTMLResponse)
async def rotate_image(request: Request):
    return templates.TemplateResponse("rotate.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)

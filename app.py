from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from starlette.status import HTTP_303_SEE_OTHER
from starlette.middleware.sessions import SessionMiddleware
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
import random
import re
import psutil
import subprocess

# Local imports
import models
from database import SessionLocal, engine
from product_data import products

# LOAD ENV VARIABLES

load_dotenv()
EMAIL = os.getenv("EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")


# DATABASE SETUP

models.Base.metadata.create_all(bind=engine)

# FASTAPI APP

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static + Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# DATABASE DEPENDENCY

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# MAIL CONFIGURATION

conf = ConnectionConfig(
    MAIL_USERNAME=EMAIL,
    MAIL_PASSWORD=APP_PASSWORD,
    MAIL_FROM=EMAIL,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)
fm = FastMail(conf)


# AUTH HELPER

def get_current_user(request: Request):
    return request.session.get("user")

# PASSWORD VALIDATION

def validate_password(password: str) -> str:
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least 1 uppercase letter."
    if not re.search(r"[@#$]", password):
        return "Password must contain at least one special character (@, #, $)."
    if len(re.findall(r"\d", password)) < 2:
        return "Password must contain at least 2 digits."
    return ""

# SIGN UP

@app.get("/Sign_up", response_class=HTMLResponse)
def sign_up_page(request: Request):
    return templates.TemplateResponse("index_su.html", {"request": request})

@app.post("/signup", response_class=HTMLResponse)
async def sign_up(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    address: str = Form(...),
    location: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    if password != confirm_password:
        return templates.TemplateResponse(
            "index_su.html", {"request": request, "error": "Passwords do not match"}
        )
    
    password_error = validate_password(password)
    if password_error:
        return templates.TemplateResponse(
            "index_su.html", {"request": request, "error": password_error}
        )
    
    existing_user = db.query(models.User).filter_by(email=email).first()
    if existing_user:
        return templates.TemplateResponse(
            "index_su.html", {"request": request, "error": "Email already registered"}
        )
    
    hashed_pw = bcrypt.hash(password)
    
    # Generate OTP + timestamp
    otp = str(random.randint(100000, 999999))
    request.session["otp"] = otp
    request.session["otp_created_at"] = datetime.now().isoformat()
    request.session["signup_data"] = {
        "name": name,
        "email": email,
        "address": address,
        "location": location,
        "password_hash": hashed_pw,
    }

    # Send OTP email
    message = MessageSchema(
        subject="Your OTP Verification Code",
        recipients=[email],
        body=f"Hello {name},\n\nYour OTP code is: {otp}\n\nIt expires in 1 minute.",
        subtype="plain"
    )
    try:
        await fm.send_message(message)
    except Exception as e:
        print("Error sending OTP email:", e)
        return templates.TemplateResponse(
            "index_su.html", {"request": request, "error": "Failed to send OTP email"}
        )
    
    return templates.TemplateResponse("verify_otp.html", {"request": request, "email": email})

# VERIFY OTP

@app.post("/verify-otp", response_class=HTMLResponse)
async def verify_otp(
    request: Request,
    otp: str = Form(...),
    db: Session = Depends(get_db),
):
    if "otp" not in request.session or "signup_data" not in request.session:
        return RedirectResponse(url="/Sign_up", status_code=HTTP_303_SEE_OTHER)
    
    otp_created_at = datetime.fromisoformat(request.session.get("otp_created_at"))
    if datetime.now() > otp_created_at + timedelta(minutes=1):
        return templates.TemplateResponse(
            "verify_otp.html",
            {"request": request, "error": "OTP expired. Please resend OTP.", "resend": True}
        )
    
    if otp != request.session["otp"]:
        return templates.TemplateResponse(
            "verify_otp.html", {"request": request, "error": "Invalid OTP"}
        )
    
    # Check duplicate email again
    data = request.session["signup_data"]
    existing_user = db.query(models.User).filter_by(email=data["email"]).first()
    if existing_user:
        del request.session["otp"]
        del request.session["otp_created_at"]
        del request.session["signup_data"]
        return templates.TemplateResponse(
            "verify_otp.html",
            {"request": request, "error": "Email already registered. Please sign in."}
        )
    
    new_user = models.User(
        name=data["name"],
        email=data["email"],
        address=data["address"],
        location=data["location"],
        password_hash=data["password_hash"],
    )
    db.add(new_user)
    db.commit()
    
    # Clear session
    del request.session["otp"]
    del request.session["otp_created_at"]
    del request.session["signup_data"]

    # Send welcome email
    welcome_msg = MessageSchema(
        subject="Welcome to Our Platform!",
        recipients=[data["email"]],
        body=f"Hello {data['name']},\n\nWelcome! to our AutoDeal Service..\n Your registration is complete.\n\nThank you!",
        subtype="plain"
    )
    try:
        await fm.send_message(welcome_msg)
    except Exception as e:
        print("Error sending welcome email:", e)

    return RedirectResponse(url="/Sign_in", status_code=HTTP_303_SEE_OTHER)

# RESEND OTP

@app.get("/resend-otp", response_class=HTMLResponse)
async def resend_otp(request: Request):
    if "signup_data" not in request.session:
        return RedirectResponse(url="/Sign_up", status_code=HTTP_303_SEE_OTHER)
    
    data = request.session["signup_data"]
    otp = str(random.randint(100000, 999999))
    request.session["otp"] = otp
    request.session["otp_created_at"] = datetime.now().isoformat()

    message = MessageSchema(
        subject="Your New OTP Verification Code",
        recipients=[data["email"]],
        body=f"Hello {data['name']},\n\nYour new OTP code is: {otp}\n\nIt expires in 1 minute.",
        subtype="plain"
    )
    try:
        await fm.send_message(message)
    except Exception as e:
        print("Error sending new OTP email:", e)
        return templates.TemplateResponse("verify_otp.html", {"request": request, "error": "Failed to resend OTP"})
    
    return templates.TemplateResponse(
        "verify_otp.html", {"request": request, "email": data["email"], "message": "New OTP sent!"}
    )

# SIGN IN / LOGOUT

@app.get("/Sign_in", response_class=HTMLResponse)
def sign_in_page(request: Request):
    return templates.TemplateResponse("index_si.html", {"request": request})

@app.post("/signin", response_class=HTMLResponse)
def sign_in(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=email).first()
    if not user or not bcrypt.verify(password, user.password_hash):
        return templates.TemplateResponse("index_si.html", {"request": request, "error": "Invalid email or password"})
    request.session["user"] = user.email
    return RedirectResponse(url="/home", status_code=HTTP_303_SEE_OTHER)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)


# HOME & PRODUCT ROUTES

@app.get("/", response_class=HTMLResponse)
async def car_front(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "products": products})

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    if not get_current_user(request):
        return RedirectResponse(url="/Sign_in", status_code=HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("index.html", {"request": request, "products": products})

@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: int):
    if not get_current_user(request):
        return RedirectResponse(url="/Sign_in", status_code=HTTP_303_SEE_OTHER)
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return HTMLResponse(content="Product not found", status_code=404)
    return templates.TemplateResponse("rent.html", {"request": request, "product": product})

@app.get("/predict")
def start_streamlit():
    # Check if Streamlit already running
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        cmdline = ' '.join(proc.info.get('cmdline') or [])
        if "streamlit" in cmdline and "main.py" in cmdline:
            return {"message": "Streamlit already running"}
    # Launch Streamlit
    subprocess.Popen(["streamlit", "run", "main.py"])
    return {"message": "Streamlit launched"}


from product_data import products

# --- add to app.py (below your existing routes) ---
from fastapi import Form

# show buy confirmation page (shows buy price = left side of '|')
@app.get("/buy/{product_id}", response_class=HTMLResponse)
async def buy_page(request: Request, product_id: int):
    if not get_current_user(request):
        return RedirectResponse(url="/Sign_in", status_code=HTTP_303_SEE_OTHER)

    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return HTMLResponse(content="Product not found", status_code=404)

    # parse buy price (left of '|')
    raw_price = product.get("price", "")
    buy_price = raw_price.split("|")[0].strip() if "|" in raw_price else raw_price.strip()

    return templates.TemplateResponse("confirm_buy.html", {
        "request": request,
        "product": product,
        "buy_price": buy_price
    })

# handle buy confirmation POST

@app.post("/confirm_buy", response_class=HTMLResponse)
async def confirm_buy(
    request: Request,
    car_id: int = Form(...),
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(...),
    db: Session = Depends(get_db)
):
    # Find the selected product
    product = next((p for p in products if p["id"] == car_id), None)
    if not product:
        return HTMLResponse(content="Product not found", status_code=404)

    # Extract and clean price
    raw_price = product.get("price", "")
    buy_price = raw_price.split("|")[0].strip() if "|" in raw_price else raw_price.strip()
    clean_price = float(buy_price.replace("$", "").replace(",", "").strip())

    # Save to database
    buy_record = models.Buy(
        customer_name=customer_name,
        email=customer_email,
        phone=customer_phone,
        car_id=car_id,
        car_name=product["name"],
        price=clean_price
    )
    db.add(buy_record)
    db.commit()
    db.refresh(buy_record)

    
    return templates.TemplateResponse("success_buy.html", {
        "request": request,
        "product_name": product["name"],
        "buy_price": buy_price,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "product":product
    })



# show rent confirmation page (shows rent price = right side of '|')
@app.get("/rent/{product_id}", response_class=HTMLResponse)
async def rent_page(request: Request, product_id: int):
    if not get_current_user(request):
        return RedirectResponse(url="/Sign_in", status_code=HTTP_303_SEE_OTHER)

    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return HTMLResponse(content="Product not found", status_code=404)

    raw_price = product.get("price", "")
    # rent price usually after '|'
    rent_price = raw_price.split("|")[1].strip() if "|" in raw_price and len(raw_price.split("|")) > 1 else raw_price.strip()

    return templates.TemplateResponse("rent_confirm.html", {
        "request": request,
        "product": product,
        "rent_price": rent_price
    })


# handle rent confirmation POST
@app.post("/confirm_rent", response_class=HTMLResponse)
async def confirm_rent(
    request: Request,
    car_id: int = Form(...),
    customer_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    duration: str = Form(...),
    pick_up_date: str = Form(...),
    db: Session = Depends(get_db)
):
    product = next((p for p in products if p["id"] == car_id), None)
    if not product:
        return HTMLResponse(content="Product not found", status_code=404)

    # extract raw price
    raw_price = product.get("price", "")
    rent_price = raw_price.split("|")[1].strip() if "|" in raw_price and len(raw_price.split("|")) > 1 else raw_price.strip()

    # clean to float before inserting into DB
    clean_rent_price = float(
        rent_price.replace("$", "").replace("/month", "").replace(",", "").strip()
    )
    duration_int = int(duration)
    total_rent=clean_rent_price*duration_int
    pick_up_date_obj = datetime.strptime(pick_up_date, "%d-%m-%Y").date()


    rent_record = models.Rent(
        customer_name=customer_name,
        email=email,
        phone=phone,
        duration=duration,
        car_id=car_id,
        car_name=product["name"],
        rent_price_per_month=clean_rent_price,   
        total_rent = float(clean_rent_price) * float(duration),
        pick_up_date=pick_up_date_obj

    )

    db.add(rent_record)
    db.commit()
    db.refresh(rent_record)

    return templates.TemplateResponse("success_rent.html", {
    "request": request,
    "rent_price": total_rent,          
    "customer_name": customer_name,
    "customer_email": email,
    "customer_phone": phone,
    "product": product,
    "duration": duration,
    "pick_up_date": pick_up_date_obj.strftime("%d-%m-%Y")  
})



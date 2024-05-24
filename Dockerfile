# 베이스 이미지 설정
FROM python:3.9

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일 복사
COPY requirements.txt requirements.txt
COPY . .

# 의존성 설치
RUN pip install -r requirements.txt

# 컨테이너 시작 시 실행할 명령
CMD ["python", "bot.py"]

import time
import board
import busio
import digitalio
import adafruit_dht
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import mysql.connector
from mysql.connector import Error
import RPi.GPIO as GPIO
from datetime import datetime

# Khởi tạo cảm biến DHT11
dht_device = adafruit_dht.DHT11(board.D6)

# Thiết lập GPIO cho LED
LED_PINS = [5, 20, 21]
GPIO.setmode(GPIO.BCM)
for pin in LED_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Khởi tạo SPI cho MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D8)  # Chân CS, có thể thay đổi nếu cần
mcp = MCP.MCP3008(spi, cs)

# Kênh cảm biến
light_channel = AnalogIn(mcp, MCP.P0)  # Cảm biến ánh sáng
soil_channel = AnalogIn(mcp, MCP.P1)   # Cảm biến độ ẩm đất

# Hàm chuyển đổi giá trị ADC ánh sáng sang lux (tùy cảm biến và cầu phân áp)
def convert_to_lux(adc_value):
    return round((adc_value / 65535) * 1000, 2)  # Giả sử tối đa 1000 lux

# Hàm chuyển đổi giá trị ADC đất sang phần trăm (có thể cần hiệu chỉnh)
def convert_to_soil_percent(adc_value):
    return round((1 - adc_value / 65535) * 100, 2)

# Kết nối MariaDB
try:
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='1',
        database='env'
    )
    cursor = connection.cursor()
    print("✅ Kết nối MariaDB thành công")
except Error as e:
    print(f"❌ Lỗi kết nối MariaDB: {e}")
    exit(1)

# Tạo bảng nếu chưa tồn tại
create_table_query = """
CREATE TABLE IF NOT EXISTS sensor_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temperature FLOAT NOT NULL,
    humidity FLOAT NOT NULL,
    light_lux FLOAT NOT NULL,
    soil_moisture_percent FLOAT NOT NULL,
    reading_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
cursor.execute(create_table_query)
connection.commit()

# Vòng lặp chính
try:
    while True:
        try:
            temperature = dht_device.temperature
            humidity = dht_device.humidity
            light_lux = convert_to_lux(light_channel.value)
            soil_percent = convert_to_soil_percent(soil_channel.value)

            if temperature is not None and humidity is not None:
                print(f"[{datetime.now()}] Nhiệt độ: {temperature}°C, Độ ẩm: {humidity}%, Lux: {light_lux}, Đất: {soil_percent}%")

                # Lưu dữ liệu vào DB
                insert_query = """
                INSERT INTO sensor_data (temperature, humidity, light_lux, soil_moisture_percent)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query, (temperature, humidity, light_lux, soil_percent))
                connection.commit()

                # Điều khiển LED (ví dụ: bật nếu vượt ngưỡng)
                GPIO.output(21, temperature > 30)
                #GPIO.output(5, humidity < 40)
                GPIO.output(20, soil_percent < 30)
            else:
                print("⚠️ Không đọc được dữ liệu DHT11")

        except RuntimeError as e:
            print(f"❗ Lỗi cảm biến DHT11: {e}")
        
        time.sleep(2)

except KeyboardInterrupt:
    print("\n🛑 Dừng chương trình")
finally:
    cursor.close()
    connection.close()
    dht_device.exit()
    GPIO.cleanup()

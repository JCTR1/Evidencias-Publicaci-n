import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import rasterio
from pyproj import Transformer

# Funciones GNSS

def nmea_to_decimal(coord, direction):
    if '.' not in coord:
        return None  
    izquierda, derecha = coord.split('.', 1)
    minutos_str = izquierda[-2:] + '.' + derecha  
    try:
        minutos = float(minutos_str)
    except ValueError:
        return None
    grados_str = izquierda[:-2]
    try:
        grados = float(grados_str) if grados_str else 0.0
    except ValueError:
        return None
    valor_decimal = grados + minutos / 60.0
    if direction in ['S', 'W']:
        valor_decimal = -valor_decimal
    return valor_decimal

def parse_gga(sentence):
    parts = sentence.split(',')
    if not parts or not parts[0].strip().endswith("GGA"):
        return None
    try:
        lat = nmea_to_decimal(parts[2], parts[3])
        lon = nmea_to_decimal(parts[4], parts[5])
        altitud_msl = float(parts[9])
        return lat, lon, altitud_msl
    except (IndexError, ValueError):
        return None

def obtener_elevacion_dem(dataset, transformer, lat, lon):
    utm_x, utm_y = transformer.transform(lon, lat)
    row, col = dataset.index(utm_x, utm_y)
    elevacion = dataset.read(1)[row, col]
    return elevacion

# Interfaz gráfica

class GNSSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Altitud GNSS")

        self.file_path = tk.StringVar()
        self.com_port = tk.StringVar()
        self.altitud_text = tk.StringVar(value="Altura sobre el terreno: -")

        # Selector de archivo DEM
        tk.Label(root, text="Archivo DEM:").pack()
        tk.Entry(root, textvariable=self.file_path, width=60).pack()
        tk.Button(root, text="Seleccionar archivo...", command=self.seleccionar_archivo).pack()

        # Selector de puerto COM
        tk.Label(root, text="Puerto COM:").pack(pady=(10, 0))
        self.combobox = ttk.Combobox(root, textvariable=self.com_port, values=self.puertos_disponibles(), state="readonly")
        self.combobox.pack()

        # Botón de inicio
        tk.Button(root, text="Iniciar lectura GNSS", command=self.iniciar_lectura).pack(pady=10)

        # Etiqueta para "Altitud GPS (MSL)"
        tk.Label(root, text="Altura MSL:", font=("Arial", 14)).pack(pady=(20, 0))
        self.valor_msl_label = tk.Label(root, text="- m", font=("Arial", 28))
        self.valor_msl_label.pack(pady=(5, 10))

        # Etiqueta para "Altura sobre el terreno"
        tk.Label(root, text="Altura sobre el terreno:", font=("Arial", 14)).pack()
        self.valor_altura_label = tk.Label(root, text="- m", font=("Arial", 32, "bold"))
        self.valor_altura_label.pack(pady=(5, 20))


        self.running = False

    def seleccionar_archivo(self):
        ruta = filedialog.askopenfilename(filetypes=[("Archivos TIF", "*.tif"), ("Todos los archivos", "*.*")])
        if ruta:
            self.file_path.set(ruta)

    def puertos_disponibles(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def iniciar_lectura(self):
        if not self.file_path.get() or not self.com_port.get():
            messagebox.showerror("Error", "Selecciona un archivo DEM y un puerto COM.")
            return
        threading.Thread(target=self.leer_datos, daemon=True).start()

    def leer_datos(self):
        self.running = True
        try:
            ser = serial.Serial(self.com_port.get(), 9600, timeout=1)
            dem_dataset = rasterio.open(self.file_path.get())
            dem_crs = dem_dataset.crs
            transformer = Transformer.from_crs("EPSG:4326", dem_crs, always_xy=True)

            while self.running:
                try:
                    line = ser.readline().decode('ascii', errors='ignore').strip()
                    if line and line.split(',')[0].strip().endswith("GGA"):
                        resultado = parse_gga(line)
                        if resultado:
                            lat, lon, gps_altitud = resultado
                            elevacion_terreno = obtener_elevacion_dem(dem_dataset, transformer, lat, lon)
                            altura_suelo = gps_altitud - elevacion_terreno
                            self.valor_msl_label.config(text=f"{gps_altitud:.2f} m")
                            self.valor_altura_label.config(text=f"{altura_suelo:.2f} m")


                except Exception as e:
                    self.altitud_text.set(f"Error: {e}")
        except Exception as e:
            messagebox.showerror("Error al abrir el puerto o el DEM", str(e))
            self.running = False

# Lanzamiento del programa

if __name__ == "__main__":
    root = tk.Tk()
    app = GNSSApp(root)
    root.mainloop()

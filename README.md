# codigosnovilloalegre

# Sistema de QR Dinámicos con Streamlit

Esta es una aplicación web todo-en-uno para la gestión de códigos QR de un solo uso para descuentos, regalos o canjes.

## 🚀 Funcionalidades

El sistema simula 3 roles de usuario diferentes:

1.  **Creador (Creator)**:
    * Puede generar códigos QR únicos o en lotes.
    * Asigna propiedades dinámicas a cada QR: descripción, categoría, fecha de vigencia y sucursales permitidas.
    * Descarga las "tarjetas de regalo" con el QR incrustado.

2.  **Cajero (Cashier)**:
    * Puede "escanear" un QR subiendo una foto del mismo.
    * La app valida si el QR es Válido, ya fue Canjeado, está Expirado o no pertenece a su sucursal.
    * Si es válido, puede registrar el canje asociándolo a un número de factura.

3.  **Administrador (Admin)**:
    * Tiene acceso a todos los permisos de un Creador.
    * Puede ver un panel de reportes con filtros por estado (canjeado/no canjeado) y rango de fechas.
    * Visualiza métricas clave sobre el uso de los QRs.

## ⚙️ ¿Cómo ejecutarlo localmente?

1.  **Clona el repositorio:**
    ```bash
    git clone <URL-de-tu-repositorio>
    cd <nombre-del-repositorio>
    ```

2.  **Crea un entorno virtual (recomendado):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    ```

3.  **Instala las dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ejecuta la aplicación Streamlit:**
    ```bash
    streamlit run app.py
    ```

5.  Abre tu navegador y ve a `http://localhost:8501`.

## ☁️ Despliegue en Streamlit Community Cloud

Puedes desplegar esta aplicación gratis siguiendo estos pasos:

1.  Sube los archivos `app.py` y `requirements.txt` a un repositorio público de GitHub.
2.  Ve a [share.streamlit.io](https://share.streamlit.io) y regístrate con tu cuenta de GitHub.
3.  Haz clic en "New app" y selecciona el repositorio que acabas de crear.
4.  Asegúrate de que el archivo principal sea `app.py`.
5.  ¡Haz clic en "Deploy!" y listo!

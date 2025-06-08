# KMD - Komodo Package Manager

KMD (Komodo Package Manager) es un gestor de paquetes liviano y extensible diseñado para sistemas Windows. Su propósito es facilitar la instalación, desinstalación y actualización de software empaquetado en archivos `.zip` con estructura predefinida.

Los paquetes son gestionados mediante un archivo `index.json` alojado en GitHub Pages, lo que permite a los desarrolladores distribuir sus aplicaciones de forma sencilla y sin necesidad de servidores complejos.

🌐 URL del index:  
https://ceccpro.github.io/kmd-db/index.json

### Características

- 📦 Instalación y desinstalación de paquetes con dependencias
- 🔄 Actualización individual o masiva de paquetes
- 🔍 Búsqueda de paquetes por nombre
- 📁 Manejo de `postInstallScript` y validación por hash
- 📝 Registro local de paquetes instalados

### Formato de ID
Los paquetes utilizan el formato: `Autor@NombrePaquete`, lo que permite un control preciso de versiones y una organización modular.

> Ejemplo: `CeccPro@testApp`

## 🤝 Contribuciones

¿Quieres meter paquetes nuevos o mejorar el repositorio? ¡Hazlo directo aquí!

Solo sigue estos pasos:

1. *Clona el repositorio*:
```bash
git clone https://github.com/ceccpro/kmd-db.git
cd kmd
```

2. *Crea una nueva rama para tus cambios*:
```bash
git checkout -b mi-paquete
```

3. *Agrega o modifica los archivos que quieras (por ejemplo, actualiza index.json para agregar paquetes nuevos).*
   
4. *Haz commit y push a tu rama:*
```bash
git add .
git commit -m "Agrego paquete nuevo: nombrePaquete"
git push origin mi-paquete
```

5. *Crea un Pull Request desde tu rama hacia main en GitHub para que revisemos tus cambios.*

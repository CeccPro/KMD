# KMD - Komodo Package Manager

KMD (Komodo Package Manager) es un gestor de paquetes liviano y extensible diseñado para sistemas Windows. Su propósito es facilitar la instalación, desinstalación y actualización de software empaquetado en archivos `.zip` con estructura predefinida.

Los paquetes son gestionados mediante un archivo `index.json` alojado en GitHub Pages, lo que permite a los desarrolladores distribuir sus aplicaciones de forma sencilla y sin necesidad de servidores complejos.

🌐 URL del index:  
https://ceccpro.github.io/kmd.db/index.json

### Características

- 📦 Instalación y desinstalación de paquetes con dependencias
- 🔄 Actualización individual o masiva de paquetes
- 🔍 Búsqueda de paquetes por nombre
- 📁 Manejo de `postInstallScript` y validación por hash
- 📝 Registro local de paquetes instalados

### Formato de ID
Los paquetes utilizan el formato: `Autor.NombrePaquete@Versión`, lo que permite un control preciso de versiones y una organización modular.

> Ejemplo: `CeccPro.testApp@1.0.0`

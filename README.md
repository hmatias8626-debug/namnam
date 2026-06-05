# Ñam Ñam Web v2

Primera fase básica en Streamlit + Supabase con login.

## Incluye
- Login básico desde `namnam_usuarios`.
- Tablas con prefijo `namnam_`.
- Productos: alta, modificación, baja lógica e importación CSV.
- Clientes: alta, modificación, baja lógica.
- Pedidos: creación, detalle y estados.
- Estados: Pendiente, En preparación, Listo, En reparto, Entregado.
- Stock simple: carga/ajuste manual.
- Caja básica: ingresos, egresos y saldo.
- Diseño oscuro/dorado inspirado en Ñam Ñam.

## Usuario inicial
Si ejecutás `sql/schema_supabase.sql`, se crea:

```text
Usuario: matias
Clave: 1234
Rol: admin
```

Después conviene cambiar esa clave.

## Instalación local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Supabase
1. Ir a Supabase > SQL Editor.
2. Ejecutar `sql/schema_supabase.sql`.
3. Copiar `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml`.
4. Completar:
```toml
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "TU_ANON_KEY"
```

## Streamlit Cloud
En App settings > Secrets pegar el mismo contenido de `secrets.toml`.

## Productos iniciales
Hay un archivo opcional en:

`data/productos_iniciales.csv`

Se puede importar desde la pantalla Productos.

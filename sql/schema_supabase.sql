-- Ñam Ñam Web v2 - Supabase/PostgreSQL
-- Tablas con prefijo namnam_ + login básico.
-- Ejecutar en Supabase > SQL Editor.

CREATE TABLE IF NOT EXISTS namnam_usuarios (
    id BIGSERIAL PRIMARY KEY,
    usuario TEXT UNIQUE NOT NULL,
    clave TEXT NOT NULL,
    rol TEXT DEFAULT 'admin',
    activo BOOLEAN DEFAULT TRUE,
    fecha_alta TIMESTAMP DEFAULT NOW()
);

INSERT INTO namnam_usuarios (usuario, clave, rol, activo)
VALUES ('matias', '1234', 'admin', TRUE)
ON CONFLICT (usuario) DO NOTHING;

CREATE TABLE IF NOT EXISTS namnam_productos (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    categoria TEXT NOT NULL,
    unidad TEXT DEFAULT 'unidad',
    precio_venta NUMERIC(12,2) DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE,
    fecha_alta TIMESTAMP DEFAULT NOW()
);

ALTER TABLE namnam_productos
ADD COLUMN IF NOT EXISTS unidad TEXT DEFAULT 'unidad';

CREATE TABLE IF NOT EXISTS namnam_clientes (
    id BIGSERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    telefono TEXT,
    direccion TEXT,
    observaciones TEXT,
    activo BOOLEAN DEFAULT TRUE,
    fecha_alta TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS namnam_pedidos (
    id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT REFERENCES namnam_clientes(id),
    cliente_nombre TEXT,
    fecha TIMESTAMP DEFAULT NOW(),
    estado TEXT DEFAULT 'Pendiente',
    total NUMERIC(12,2) DEFAULT 0,
    observaciones TEXT
);

ALTER TABLE namnam_pedidos
ADD COLUMN IF NOT EXISTS cliente_nombre TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_estado_pedido'
    ) THEN
        ALTER TABLE namnam_pedidos
        ADD CONSTRAINT chk_estado_pedido
        CHECK (estado IN ('Pendiente','En preparación','Listo','En reparto','Entregado'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS namnam_pedido_detalles (
    id BIGSERIAL PRIMARY KEY,
    pedido_id BIGINT REFERENCES namnam_pedidos(id) ON DELETE CASCADE,
    producto_id BIGINT REFERENCES namnam_productos(id),
    producto_nombre TEXT,
    cantidad NUMERIC(12,2) NOT NULL,
    precio_unitario NUMERIC(12,2) NOT NULL,
    subtotal NUMERIC(12,2) NOT NULL
);

ALTER TABLE namnam_pedido_detalles
ADD COLUMN IF NOT EXISTS producto_nombre TEXT;

CREATE TABLE IF NOT EXISTS namnam_stock (
    id BIGSERIAL PRIMARY KEY,
    producto_id BIGINT REFERENCES namnam_productos(id),
    cantidad NUMERIC(12,2) DEFAULT 0,
    ultima_actualizacion TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS namnam_caja (
    id BIGSERIAL PRIMARY KEY,
    fecha TIMESTAMP DEFAULT NOW(),
    tipo TEXT NOT NULL,
    concepto TEXT NOT NULL,
    importe NUMERIC(12,2) NOT NULL,
    observaciones TEXT
);

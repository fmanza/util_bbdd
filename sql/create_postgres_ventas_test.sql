-- 1. Crear el esquema de prueba
CREATE SCHEMA ventas_test;

-- 2. Crear tabla de clientes
CREATE TABLE ventas_test.clientes (
    cliente_id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL
);

-- 3. Crear tabla de productos
CREATE TABLE ventas_test.productos (
    producto_id SERIAL PRIMARY KEY,
    nombre_producto VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL
);

-- 4. Crear tabla de pedidos (relación 1-N con clientes)
CREATE TABLE ventas_test.pedidos (
    pedido_id SERIAL PRIMARY KEY,
    cliente_id INT REFERENCES ventas_test.clientes(cliente_id),
    fecha_pedido DATE DEFAULT CURRENT_DATE
);

-- 5. Crear tabla intermedia de detalles (relación N-M entre pedidos y productos)
CREATE TABLE ventas_test.detalle_pedidos (
    detalle_id SERIAL PRIMARY KEY,
    pedido_id INT REFERENCES ventas_test.pedidos(pedido_id),
    producto_id INT REFERENCES ventas_test.productos(producto_id),
    cantidad INT NOT NULL
);

-- 6. Insertar datos de ejemplo
INSERT INTO ventas_test.clientes (nombre, email) VALUES
('Juan Pérez', 'juan@example.com'),
('Ana Gómez', 'ana@example.com');

INSERT INTO ventas_test.productos (nombre_producto, precio) VALUES
('Laptop', 1200.00),
('Ratón', 25.50),
('Teclado', 45.00);

INSERT INTO ventas_test.pedidos (cliente_id) VALUES (1), (2);

INSERT INTO ventas_test.detalle_pedidos (pedido_id, producto_id, cantidad) VALUES
(1, 1, 1), -- Juan compró 1 Laptop
(1, 2, 2), -- Juan compró 2 Ratones
(2, 3, 1); -- Ana compró 1 Teclado

-- 7. Consulta de prueba para verificar relaciones
SELECT
    c.nombre AS cliente,
    p.pedido_id,
    pr.nombre_producto,
    dp.cantidad,
    (pr.precio * dp.cantidad) AS total_linea
FROM ventas_test.clientes c
JOIN ventas_test.pedidos p ON c.cliente_id = p.cliente_id
JOIN ventas_test.detalle_pedidos dp ON p.pedido_id = dp.pedido_id
JOIN ventas_test.productos pr ON dp.producto_id = pr.producto_id;

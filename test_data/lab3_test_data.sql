-- Очищаем таблицы перед заполнением (чтобы не было конфликтов ID)
TRUNCATE catalog.product_categories, catalog.warehouses, catalog.products, sales.orders, sales.order_items RESTART IDENTITY CASCADE;

-- 1. Наполняем категории товаров
INSERT INTO catalog.product_categories (name) VALUES
('Смартфоны и гаджеты'),
('Ноутбуки и ПК'),
('Мониторы и ТВ'),
('Аксессуары');

-- 2. Наполняем склады
-- Первый склад автоматически становится центральным (флаг true)
INSERT INTO catalog.warehouses (city, address, label, is_central) VALUES
('Москва', 'ул. Ломоносова, д. 5, стр. 1', 'Центральный хаб', true),
('Санкт-Петербург', 'Невский проспект, д. 45', 'Торговая точка Центр', false),
('Новосибирск', 'ул. Ленина, д. 12', 'Сибирский филиал', false);

-- 3. Наполняем товары (связываем с ID категорий: 1 - смартфоны, 2 - ноуты, 3 - мониторы, 4 - уши)
INSERT INTO catalog.products (sku, name, price, product_category_id) VALUES
('IPH15PRO-128', 'Apple iPhone 15 Pro 128GB', 95000.00, 1),
('SAM-S24ULTRA', 'Samsung Galaxy S24 Ultra', 115000.00, 1),
('MAC-AIR-M3', 'MacBook Air 13 M3 16/512GB', 140000.00, 2),
('ASUS-ROG-G16', 'ASUS ROG Strix G16 Gaming', 165000.00, 2),
('MSI-MAG-27', 'Монитор MSI MAG 27" IPS 144Hz', 24500.00, 3),
('LG-OLED-55', 'Телевизор LG OLED 55"', 135000.00, 3),
('SND-WH1000', 'Наушники Sony WH-1000XM5', 35000.00, 4),
('LOG-GPRO-X', 'Мышь Logitech G Pro X Superlight', 12500.00, 4);

-- 4. Создаем тестовые заказы (связываем с ID складов: 1 - Москва, 2 - Питер)
-- Первый заказ — черновик (unpublished)
INSERT INTO sales.orders (status, total_amount, warehouse_id) VALUES
('unpublished', 0.00, 1);

-- Второй заказ — уже опубликованный (new), его нельзя будет менять/удалять в REPL
INSERT INTO sales.orders (status, total_amount, warehouse_id) VALUES
('new', 0.00, 2);

-- 5. Заполняем позиции для созданных заказов (order_items)
-- Позиции для Заказа #1 (Черновик в Москве): 2 айфона и 1 мышка
INSERT INTO sales.order_items (order_id, product_id, price, quantity) VALUES
(1, 1, 95000.00, 2),  -- iPhone 15 Pro
(1, 8, 12500.00, 1);  -- Мышь Logitech

-- Позиции для Заказа #2 (Опубликован в Питере): 1 Макбук и 1 уши Sony
INSERT INTO sales.order_items (order_id, product_id, price, quantity) VALUES
(2, 3, 140000.00, 1), -- MacBook Air
(2, 7, 35000.00, 1);  -- Наушники Sony

-- 6. Автоматически пересчитываем total_amount для наших заказов на основе позиций
UPDATE sales.orders o
SET total_amount = (
    SELECT COALESCE(SUM(oi.price * oi.quantity), 0)
    FROM sales.order_items oi
    WHERE oi.order_id = o.id
)
WHERE o.id > 0;

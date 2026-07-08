CREATE SCHEMA IF NOT EXISTS sales;

CREATE TABLE IF NOT EXISTS sales.orders
(
    id           SERIAL PRIMARY KEY,
    status       TEXT    NOT NULL DEFAULT 'unpublished',
    total_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    created_at   TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    warehouse_id INT            NOT NULL,
    CONSTRAINT fk_order_warehouse
        FOREIGN KEY (warehouse_id)
            REFERENCES catalog.warehouses (id)
            ON DELETE RESTRICT,
    CONSTRAINT chk_order_status
        CHECK (status IN ('unpublished', 'new', 'processing', 'pending', 'packing', 'shipped')),
    CONSTRAINT chk_order_total_amount
        CHECK (total_amount >= 0.00)
);

CREATE TABLE IF NOT EXISTS sales.order_items
(
    order_id   INT            NOT NULL,
    product_id INT            NOT NULL,
    price      DECIMAL(12, 2) NOT NULL,
    quantity   INT            NOT NULL,
    CONSTRAINT pk_order_items
        PRIMARY KEY (order_id, product_id),
    CONSTRAINT fk_item_order
        FOREIGN KEY (order_id)
            REFERENCES sales.orders (id)
            ON DELETE CASCADE,
    CONSTRAINT fk_item_product
        FOREIGN KEY (product_id)
            REFERENCES catalog.products (id)
            ON DELETE RESTRICT,
    CONSTRAINT chk_item_quantity
        CHECK (quantity > 0),
    CONSTRAINT chk_item_price
        CHECK (price >= 0.00)
);


DROP TABLE IF EXISTS catalog.products CASCADE;
DROP TABLE IF EXISTS catalog.warehouses CASCADE;
DROP TABLE IF EXISTS catalog.product_categories CASCADE;
DROP TABLE IF EXISTS catalog.categories CASCADE;

CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE catalog.product_categories
(
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    CONSTRAINT uq_category_name UNIQUE (name),
    CONSTRAINT chk_category_name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE TABLE catalog.warehouses
(
    id         SERIAL PRIMARY KEY,
    city       TEXT NOT NULL,
    address    TEXT         NOT NULL,
    label      TEXT,
    is_central BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_warehouse_label UNIQUE (label),
    CONSTRAINT chk_warehouse_city CHECK (length(trim(city)) > 0),
    CONSTRAINT chk_warehouse_address CHECK (length(trim(address)) > 0)
);

CREATE TABLE catalog.products
(
    id                  SERIAL PRIMARY KEY,
    sku                 TEXT NOT NULL,
    name                TEXT        NOT NULL,
    price               DECIMAL(12, 2)     NOT NULL,
    product_category_id INT                NOT NULL,
    CONSTRAINT fk_product_category
        FOREIGN KEY (product_category_id)
            REFERENCES catalog.product_categories (id)
            ON DELETE RESTRICT,
    CONSTRAINT uq_product_sku UNIQUE (sku),
    CONSTRAINT chk_product_price CHECK (price >= 0.00),
    CONSTRAINT chk_product_name_not_empty CHECK (length(trim(name)) > 0)
);

DROP TABLE IF EXISTS catalog.products CASCADE;
DROP TABLE IF EXISTS catalog.warehouses CASCADE;
DROP TABLE IF EXISTS catalog.product_categories CASCADE;
DROP TABLE IF EXISTS catalog.categories CASCADE;

CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE catalog.product_categories
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE catalog.warehouses
(
    id         SERIAL PRIMARY KEY,
    city       VARCHAR(255) NOT NULL,
    address    TEXT         NOT NULL,
    label      VARCHAR(255),
    is_central BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE catalog.products
(
    id                  SERIAL PRIMARY KEY,
    sku                 VARCHAR(30) UNIQUE NOT NULL,
    name                VARCHAR(255)       NOT NULL,
    price               DECIMAL(12, 2)     NOT NULL,
    product_category_id INT                NOT NULL,
    CONSTRAINT fk_product_category
        FOREIGN KEY (product_category_id)
            REFERENCES catalog.product_categories (id)
            ON DELETE RESTRICT
);

CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    country VARCHAR(80) NOT NULL
);

CREATE TABLE employees (
    id UUID PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    email VARCHAR(180) NOT NULL UNIQUE,
    salary NUMERIC(12, 2) NOT NULL,
    hired_at DATE NOT NULL,
    is_active BOOLEAN NOT NULL
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    department_id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    started_at TIMESTAMP NOT NULL,
    CONSTRAINT fk_project_department
        FOREIGN KEY (department_id) REFERENCES departments(id)
);


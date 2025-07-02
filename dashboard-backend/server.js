const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
app.use(express.json()); // Для парсинга JSON в теле запросов

// Настройки подключения к базе
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://user:password@localhost:5432/yourdb',
  ssl: process.env.DATABASE_URL ? { rejectUnauthorized: false } : false,
});

// API для получения статистики города
app.get('/api/city/:name', async (req, res) => {
  const cityName = req.params.name;

  try {
    const query = 'SELECT subs, posts, income FROM citys WHERE city = $1';
    const result = await pool.query(query, [cityName]);

    if (result.rows.length > 0) {
      res.json(result.rows[0]);
    } else {
      res.status(404).json({ error: 'Город не найден' });
    }
  } catch (err) {
    console.error(err);
    res.status(500).send('Ошибка сервера');
  }
});

// API для получения настроек по городу
app.get('/api/settings/:city', async (req, res) => {
  const city = req.params.city;

  try {
    const query = 'SELECT id, name, enabled, created_at, updated_at FROM settings WHERE city = $1 ORDER BY id';
    const result = await pool.query(query, [city]);

    if (result.rows.length > 0) {
      res.json(result.rows);
    } else {
      res.status(404).json({ error: 'Настройки для города не найдены' });
    }
  } catch (err) {
    console.error(err);
    res.status(500).send('Ошибка сервера');
  }
});

// API для обновления конкретного параметра настроек по ID
app.put('/api/settings/:id', async (req, res) => {
  const id = req.params.id;
  const { name, enabled } = req.body;

  if (typeof name !== 'string' || typeof enabled !== 'boolean') {
    return res.status(400).json({ error: 'Неверные данные для обновления' });
  }

  try {
    const query = `
      UPDATE settings
      SET name = $1, enabled = $2, updated_at = NOW()
      WHERE id = $3
      RETURNING id, city, name, enabled, created_at, updated_at
    `;
    const result = await pool.query(query, [name, enabled, id]);

    if (result.rows.length > 0) {
      res.json(result.rows[0]);
    } else {
      res.status(404).json({ error: 'Параметр не найден' });
    }
  } catch (err) {
    console.error(err);
    res.status(500).send('Ошибка сервера');
  }
});

app.listen(port, () => {
  console.log(`✅ Сервер запущен на порту ${port}`);
});

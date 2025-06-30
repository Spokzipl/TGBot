const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());

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

app.listen(port, () => {
  console.log(`✅ Сервер запущен на порту ${port}`);
});

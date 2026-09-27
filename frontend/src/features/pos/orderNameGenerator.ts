// Генератор забавных имен для заказов
const adjectives = [
  "Космический",
  "Волшебный",
  "Танцующий",
  "Летающий",
  "Сияющий",
  "Весёлый",
  "Бодрый",
  "Радужный",
  "Звёздный",
  "Солнечный",
  "Лунный",
  "Огненный",
  "Ледяной",
  "Громкий",
  "Тихий",
  "Быстрый",
  "Медленный",
  "Яркий",
  "Тёмный",
  "Сладкий",
];

const nouns = [
  "Единорог",
  "Дракон",
  "Феникс",
  "Пегас",
  "Грифон",
  "Кот",
  "Пёс",
  "Медведь",
  "Лев",
  "Тигр",
  "Панда",
  "Коала",
  "Енот",
  "Хомяк",
  "Кролик",
  "Лис",
  "Волк",
  "Сова",
  "Орёл",
  "Попугай",
];

export function generateFunnyOrderName(): string {
  const adjective = adjectives[Math.floor(Math.random() * adjectives.length)];
  const noun = nouns[Math.floor(Math.random() * nouns.length)];
  const number = Math.floor(Math.random() * 999) + 1;

  return `${adjective} ${noun} #${number}`;
}

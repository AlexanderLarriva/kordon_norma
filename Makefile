.PHONY: run sync test lint format clean help

# По умолчанию выводим справку
.DEFAULT_GOAL := help

help: ## Показать список всех доступных команд
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

run: ## Запустить приложение Streamlit
	uv run streamlit run app.py

sync: ## Установить/синхронизировать зависимости через uv
	uv sync

lint: ## Проверить код линтером ruff
	uv run ruff check .

format: ## Автоматически отформатировать код с помощью ruff
	uv run ruff format .

clean: ## Удалить файлы базы данных и кэш Python/Ruff
	rm -rf .ruff_cache __pycache__ */__pycache__ *.db

reset-db: ## Сбросить локальную базу данных (пересоздать при следующем запуске)
	rm -f database.db kordon_norma.db
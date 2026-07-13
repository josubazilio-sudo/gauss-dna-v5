@echo off
REM Script para atualizar as dependências do projeto QuantOS

REM Verifica se Python e pip estão instalados
py -m pip --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo Python e pip n�o estao instalados ou nao estao no PATH.
    echo Por favor, instale Python e assegure-se que pip esteja disponível.
    exit /B
)

REM Atualiza as dependências usando o requirements.txt
py -m pip install -r requirements.txt

echo Dependências atualizadas com sucesso!
/*
Manual bootstrap for a dedicated development/analysis database.

Run in SSMS or another confirmed SQL client while connected to the intended SQL
Server instance. Review the database name before execution. This script creates a
database only when it does not already exist; it never drops or resets one.
*/

USE [master];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @database_name sysname = N'OlistDeliveryAnalytics';

IF DB_ID(@database_name) IS NULL
BEGIN
    EXEC (N'CREATE DATABASE ' + QUOTENAME(@database_name) + N';');
    PRINT N'Created database ' + QUOTENAME(@database_name) + N'.';
END;
ELSE
BEGIN
    PRINT N'Database ' + QUOTENAME(@database_name) + N' already exists; no change made.';
END;
GO

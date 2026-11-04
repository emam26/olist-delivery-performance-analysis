/*
Create least-privilege database roles. Run this script in OlistDeliveryAnalytics
after scripts 001-006. It deliberately does not create a server login or database
user because those operations require an operator-selected identity and secret.
*/

SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_NAME() <> N'OlistDeliveryAnalytics'
    THROW 50070, 'Connect to OlistDeliveryAnalytics before running this script.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF DATABASE_PRINCIPAL_ID(N'olist_loader') IS NULL
        CREATE ROLE [olist_loader] AUTHORIZATION [dbo];

    IF DATABASE_PRINCIPAL_ID(N'olist_report_reader') IS NULL
        CREATE ROLE [olist_report_reader] AUTHORIZATION [dbo];

    GRANT SELECT, INSERT, UPDATE ON SCHEMA::[audit] TO [olist_loader];
    GRANT SELECT, INSERT ON SCHEMA::[stg] TO [olist_loader];
    GRANT SELECT ON SCHEMA::[analytics] TO [olist_loader];
    GRANT SELECT ON SCHEMA::[reporting] TO [olist_loader];
    GRANT EXECUTE ON OBJECT::[audit].[usp_run_validation] TO [olist_loader];

    GRANT SELECT ON SCHEMA::[reporting] TO [olist_report_reader];

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;

SELECT
    roles.[name] AS role_name,
    permissions.[state_desc],
    permissions.[permission_name],
    permissions.[class_desc]
FROM sys.database_principals AS roles
LEFT JOIN sys.database_permissions AS permissions
    ON permissions.[grantee_principal_id] = roles.[principal_id]
WHERE roles.[name] IN (N'olist_loader', N'olist_report_reader')
ORDER BY roles.[name], permissions.[permission_name];

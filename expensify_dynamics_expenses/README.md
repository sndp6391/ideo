# Expensify to Dynamics Expenses Migration

## About
This integration triggers an Expense report export from Expensify which is routed through an Amazon SFTP server, through S3 to a processor lambda that then sends the data to Dynamics.

Through Expensify's report export api we are able to trigger an export of all Approved and Reimbursed that have not previously been exported. Because of limitations of the Expensify api this report must be sent to a designated SFTP server we have created using EC2 on our AWS account. From there the server exports to an S3 bucket. A lambda is connected to that bucket, watching for files being created, and will pick up any new files process them, and push them into an SQS queue. From
the queue they are picked up by the Dynamics client and sent to D365.  

## Services
  - Lambda
  - EC2
  - SQS
  - S3

## Trigger
  - Schedule
  - Manual through AWS Console

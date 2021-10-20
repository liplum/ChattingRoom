﻿namespace ChattingRoom.Core.Networks;
public interface IMessage
{
    public void Serialize(dynamic json);

    public void Deserialize(dynamic json);
}

public enum Direction
{
    ServerToClient, ClientToServer
}

[AttributeUsage(AttributeTargets.Class, Inherited = false, AllowMultiple = false)]
public sealed class MsgAttribute : Attribute
{
    public string? Name
    {
        get; init;
    }
    public Direction[] Direction
    {
        get; init;
    }
    public MsgAttribute(string name, params Direction[] direction)
    {
        Name = name;
        Direction = direction;
    }

    public MsgAttribute(params Direction[] direction)
    {
        Direction = direction;
    }

    public bool Accept(Direction direction)
    {
        return Direction.Contains(direction);
    }
}